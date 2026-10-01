use numpy::PyReadonlyArray1;
use pyo3::prelude::*;

fn metrics(samples: &[f32]) -> (f64, f64, f64) {
    if samples.is_empty() {
        return (0.0, 0.0, 0.0);
    }

    let mut energy = 0.0_f64;
    let mut clipped = 0_usize;
    for &sample in samples {
        let value = sample as f64;
        energy += value * value;
        if sample.abs() >= 0.985 {
            clipped += 1;
        }
    }

    let level = (energy / samples.len() as f64).sqrt();
    let clipping = clipped as f64 / samples.len() as f64;
    let score = if level < 0.004 {
        0.2
    } else if level > 0.5 || clipping > 0.01 {
        0.35
    } else {
        let level_score = (level / 0.06).min(1.0);
        let clipping_penalty = (clipping * 20.0).min(0.8);
        (level_score * (1.0 - clipping_penalty)).clamp(0.0, 1.0)
    };

    (level, clipping, score)
}

#[pyfunction]
fn rms(samples: PyReadonlyArray1<'_, f32>) -> PyResult<f64> {
    let slice = samples.as_slice()?;
    Ok(metrics(slice).0)
}

#[pyfunction]
fn analyze(samples: PyReadonlyArray1<'_, f32>) -> PyResult<(f64, f64, f64, &'static str)> {
    let slice = samples.as_slice()?;
    let (level, clipping, score) = metrics(slice);
    let label = if clipping > 0.01 {
        "clipping"
    } else if level < 0.004 {
        "too quiet"
    } else if level > 0.5 {
        "too loud"
    } else if score >= 0.75 {
        "good"
    } else {
        "usable"
    };
    Ok((level, clipping, score, label))
}

#[pyclass]
struct AdaptiveVad {
    noise: f64,
}

#[pymethods]
impl AdaptiveVad {
    #[new]
    #[pyo3(signature = (noise=0.006))]
    fn new(noise: f64) -> Self {
        Self { noise }
    }

    #[getter]
    fn noise(&self) -> f64 {
        self.noise
    }

    fn speech(&mut self, samples: PyReadonlyArray1<'_, f32>) -> PyResult<bool> {
        let slice = samples.as_slice()?;
        let level = metrics(slice).0;
        let threshold = 0.008_f64.max(self.noise * 2.8);
        let detected = level >= threshold;
        if !detected {
            self.noise = self.noise * 0.97 + level * 0.03;
        }
        Ok(detected)
    }
}

#[pyfunction]
fn native_version() -> &'static str {
    "7.3.0"
}

#[pymodule]
fn _fast(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(rms, module)?)?;
    module.add_function(wrap_pyfunction!(analyze, module)?)?;
    module.add_function(wrap_pyfunction!(native_version, module)?)?;
    module.add_class::<AdaptiveVad>()?;
    Ok(())
}

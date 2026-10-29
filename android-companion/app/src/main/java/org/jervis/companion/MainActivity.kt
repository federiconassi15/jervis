package org.jervis.companion

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.weight
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val background = Color(0xFF04112A)
private val panel = Color(0xFF0B2349)
private val edge = Color(0xFF244E88)
private val accent = Color(0xFF8FD6FF)
private val muted = Color(0xFF8EACD3)
private val foreground = Color(0xFFE1F2FF)
private val terminalScheme = darkColorScheme(
    primary = accent, onPrimary = background,
    background = background, onBackground = foreground,
    surface = panel, onSurface = foreground,
)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = terminalScheme) {
                TerminalBlueApp()
            }
        }
    }
}

@Composable
private fun TerminalText(text: String, color: Color = foreground, size: Int = 14,
                         bold: Boolean = false) {
    Text(text = text, color = color, fontFamily = FontFamily.Monospace,
         fontSize = size.sp,
         fontWeight = if (bold) FontWeight.Bold else FontWeight.Normal)
}

@Composable
private fun TerminalPanel(title: String, content: @Composable () -> Unit) {
    Surface(
        color = panel, shape = RoundedCornerShape(12.dp),
        border = BorderStroke(1.dp, edge), modifier = Modifier.fillMaxWidth(),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            TerminalText(title, accent, 12, true)
            HorizontalDivider(color = edge)
            content()
        }
    }
}

@Composable
private fun OfflineNotice() {
    TerminalPanel("LINK / DISCONNECTED") {
        TerminalText("NO PAIRED INSTANCE", Color(0xFFF2C477), 15, true)
        TerminalText(
            "Secure relay pairing is not available in this development build. " +
                "No messages or commands will be sent.", muted, 12
        )
    }
}

@Composable
fun TerminalBlueApp() {
    val tabs = listOf("CHAT", "MISSIONS", "SYSTEM", "LOGS", "SETTINGS")
    var selected by rememberSaveable { mutableStateOf("CHAT") }
    var draft by rememberSaveable { mutableStateOf("") }
    Column(Modifier.fillMaxSize().background(background)) {
        Column(Modifier.padding(start = 16.dp, end = 16.dp, top = 24.dp, bottom = 8.dp)) {
            TerminalText("JERVIS // COMPANION", accent, 20, true)
            Spacer(Modifier.height(4.dp))
            TerminalText("TERMINAL BLUE  /  PREVIEW BUILD 0.1", muted, 11)
        }
        HorizontalDivider(color = edge)
        LazyColumn(
            modifier = Modifier.weight(1f).fillMaxWidth().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item { OfflineNotice() }
            when (selected) {
                "CHAT" -> {
                    item {
                        TerminalPanel("CONVERSATION / LOCAL") {
                            TerminalText("Remote chat requires verified pairing.", muted, 13)
                            TerminalText("› Type a message below. Sending stays disabled.", muted, 12)
                        }
                    }
                    item {
                        TerminalPanel("COMPOSE") {
                            Box(Modifier.fillMaxWidth().background(background).padding(12.dp)) {
                                BasicTextField(
                                    value = draft, onValueChange = { draft = it.take(2000) },
                                    textStyle = androidx.compose.ui.text.TextStyle(
                                        fontFamily = FontFamily.Monospace,
                                        fontSize = 14.sp, color = foreground
                                    ),
                                    modifier = Modifier.fillMaxWidth(),
                                    decorationBox = { inner ->
                                        if (draft.isBlank()) TerminalText("› Enter command_", muted)
                                        inner()
                                    },
                                )
                            }
                            Button(
                                onClick = {}, enabled = false,
                                colors = ButtonDefaults.buttonColors(containerColor = edge),
                            ) { Text("SEND  /  PAIRING REQUIRED") }
                        }
                    }
                }
                "MISSIONS" -> item {
                    TerminalPanel("MISSIONS / QUEUE") {
                        TerminalText("No linked mission service.", muted)
                        TerminalText("Mission approvals will require explicit permissions.", muted, 12)
                    }
                }
                "SYSTEM" -> item {
                    TerminalPanel("HOST / STATUS") {
                        StatusLine("INSTANCE", "NOT PAIRED")
                        StatusLine("CPU", "UNKNOWN")
                        StatusLine("MEMORY", "UNKNOWN")
                        StatusLine("OPENCLAW", "UNKNOWN")
                        TerminalText("Metrics are not simulated or guessed.", muted, 12)
                    }
                }
                "LOGS" -> item {
                    TerminalPanel("LOGS / LIVE") {
                        TerminalText("No authenticated event feed.", muted)
                        TerminalText("No private transcripts or credentials will be displayed.", muted, 12)
                    }
                }
                "SETTINGS" -> item {
                    TerminalPanel("SECURITY / PAIRING") {
                        TerminalText("Pairing and device identity setup: not yet implemented.", muted)
                        TerminalText("No passwords, access keys or embedded relay tokens.", muted, 12)
                    }
                }
            }
        }
        NavigationBar(containerColor = panel) {
            tabs.forEach { tab ->
                NavigationBarItem(
                    selected = selected == tab,
                    onClick = { selected = tab },
                    icon = { TerminalText(if (selected == tab) "◆" else "◇", accent, 12) },
                    label = { TerminalText(tab, if (selected == tab) accent else muted, 9) },
                )
            }
        }
    }
}

@Composable
private fun StatusLine(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        TerminalText(label, muted, 12)
        TerminalText(value, foreground, 12, true)
    }
}

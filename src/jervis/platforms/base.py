from abc import ABC,abstractmethod
class PlatformAdapter(ABC):
    @abstractmethod
    def install_service(self,executable,env):raise NotImplementedError
    @abstractmethod
    def remove_service(self):raise NotImplementedError
    @abstractmethod
    def service_health(self):raise NotImplementedError

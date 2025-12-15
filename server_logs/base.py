from abc import ABC, abstractmethod

class Logger(ABC):
    @abstractmethod
    def info(self, msg: str, **data): ... 

    @abstractmethod
    def debug(self, msg: str, **data): ... 

    @abstractmethod
    def warning(self, msg: str, **data): ...  

    @abstractmethod
    def error(self, msg: str, **data): ... 

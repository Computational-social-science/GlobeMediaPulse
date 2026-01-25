from abc import ABC, abstractmethod

class BaseOperator(ABC):
    """
    Abstract Base Class (ABC) defining the contract for all system operators.
    
    Architectural Role:
    This interface enforces a unified execution standard across the system's modular components
    (Intelligence, Storage, Ingestion, Parsing). It serves as the foundational polymorphism 
    mechanism, ensuring that all functional units adhere to a consistent lifecycle and 
    error-handling protocol.
    
    Design Principles:
    1.  **Modularity**: Encapsulates specific logic (e.g., classification, persistence) into 
        independent, interchangeable units.
    2.  **Extensibility**: Facilitates the addition of new capabilities (e.g., a new 
        embedding operator) without modifying the core orchestration logic.
    3.  **Standardization**: Mandates a common interface for initialization and execution, 
        simplifying dependency injection and testing.
    """
    pass

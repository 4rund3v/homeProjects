### file-grepper

The project implements the Strategy pattern
- Searcher interface defines the algorithm family
- with concrete implementations representing individual strategies
  Selected based on the configuration/flag - further reinforces the Strategy Pattern - interchangeable algorithms
- This is primarily the Strategy Pattern coupled with Factory Method pattern

Open-Closed Principle [Solid] can add a new algorithm to search without altering other components or the consumer.  
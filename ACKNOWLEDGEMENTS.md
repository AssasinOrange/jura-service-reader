# Acknowledgements

This project was possible because earlier researchers published the essentials
of Jura's service-port transport and command set:

- [Q42 coffeehack](https://github.com/Q42/coffeehack) and its
  [engineering article](https://blog.q42.nl/hacking-the-coffee-machine-5802172b17c1/)
  documented the two-useful-bits-per-carrier scheme and `RE`/`RT` memory reads.
- [Jutta-Proto/protocol-cpp](https://github.com/Jutta-Proto/protocol-cpp)
  provides a maintained C++ implementation and protocol observations.
- [oliverk71/Coffeemaker-Payment-System](https://github.com/oliverk71/Coffeemaker-Payment-System)
  demonstrates Arduino communication with several older Toptronic/Jura machines.

The code in this repository is an independent implementation. The GIGA X8c
pinout, 32-byte RT response, word addressing, memory mirror, PIN profile and
counter mapping were established from the physical machine and captures made
for this project.

# Contributing

Reports for additional models are useful when they include:

1. the exact `TY:` response;
2. connector type and pin numbering viewed from a stated side;
3. sanitised carrier examples or a synthetic reproduction of the problem;
4. the command associated with every reply;
5. a UI value or controlled before/after change that validates an address.

Do not attach raw `.jura` captures, RT reply hex, reconstructed maps or generated
reports to public issues or pull requests. They can contain PINs, counters and
configuration even when `--show-pins` was not used. Remove serial numbers,
network names and credentials from examples and screenshots. For a sensitive
report, follow [SECURITY.md](SECURITY.md) to arrange a private route first.
Treat apparent PIN values as candidates until the machine accepts them or a
controlled UI change proves the field.

Run `python -m unittest discover -s tests -p 'test_*.py' -v` before submitting
changes. Regression fixtures must use synthetic data, not private machine
dumps. See [docs/build.md](docs/build.md) for the C++ and Arduino build checks.

Keep new public firmware read-only. Submit memory writes and actuator commands
only with a clear test method and an explanation of their effects.

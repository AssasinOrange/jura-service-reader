# Contributing

Reports for additional models are useful when they include:

1. the exact `TY:` response;
2. connector type and pin numbering viewed from a stated side;
3. raw carrier bytes or an unedited `.jura` capture;
4. the command associated with every reply;
5. a UI value or controlled before/after change that validates an address.

Remove serial numbers, network names and credentials you do not want to make
public. Treat apparent PIN values as candidates until the machine accepts them
or a controlled UI change proves the field.

Keep new public firmware read-only. Submit memory writes and actuator commands
only with a clear test method and an explanation of their effects.

# Maintaining Cairystal in plain language

As the crystallographer, specify what evidence permits a decision, what the customer should see, and what would make you stop for review. The maintenance agent can implement those decisions.

> When [specific situation] occurs, the current version [observed behavior]. I want [expected behavior]. Show [observable result]. Try [permitted example], then [counterexample that could cause a wrong decision]. Keep the current version and show the comparison and remaining issues.

For example, when a paired experiment record contains the colour and habit but lacks dimensions, ask only for dimensions. Repeat with a record belonging to another specimen. Inspect the actual question and exported fields. Example dimensions belong in a hint until confirmed as measurements.

| Scenario | What to inspect |
|---|---|
| Raw HKL, starting instructions, possible elements, no 2D graph | The log identifies the actual input and supported solving route, or records the missing evidence. |
| Two pasted official alerts, one with no documented route | Both full IDs and their reported levels remain visible. Known routes identify evidence to examine. Unmapped IDs are preserved for review. Looking up a route leaves model files intact. |
| A finished model and an interrupted PDF download | An existing verified receipt for the frozen CIF resumes report retrieval. Check all four customer files or the recorded incomplete status. |

For speed changes, alternate old and new runs on the same authorized raw data and compare each stage. For a scientific rule, test an applicable sample and a case that requires review. Inspect atom identities, positions, occupancies, displacement parameters, refinement metrics and specific alert codes. Label untested outcomes explicitly.

In Codex, ask `$skill-creator` to turn the requirement into skill behavior. Ask `$cli-creator` when a repeated operation needs a reusable command and a stable result. Customers can use Cairystal independently of these maintenance tools.

Ask the agent to demonstrate these cases: A’s PCF and HKL reuse only paired fields, a different HKL is rejected, repeated alerts keep both atom descriptions, and a one-byte change to the selected CIF stops receipt recovery.

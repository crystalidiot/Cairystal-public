Run with the configured Python environment and scripts on PYTHONPATH:

For a bounded offline suite including intake, common disorder, A/B and final-delivery gates, use the portable runner from the skill directory:

    python -B scripts/portable_tests.py --output NEW_TEST_DIRECTORY

It records the tested modules, failures and elapsed time, and never overwrites an existing output. It does not invoke native solvers or upload data. Passing this suite is not a full installation or scientific correctness check. Use the following discovery command for the additional tests in this folder:

    python -m unittest discover -s tests -p "test_*.py" -v

Requires Gemmi; Fourier tests also require NumPy. Fixtures are synthetic; retrospective native evidence is intentionally outside the portable skill. The existing scripts/test_crystal_autorun.py is a separate 24-test regression.

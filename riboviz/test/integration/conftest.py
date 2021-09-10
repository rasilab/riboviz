"""
pytest plugin file for integration tests.

This allows pytest to take in additional command-line parameters to
pass onto integration test modules:

* ``--expected=<DIRECTORY>``: Directory with expected data files,
  against which files specified in the configuration file (see below)
  will be checked.
* ``--skip-workflow``: Workflow will not be run prior to checking data
  files. This can be used to check existing files generated by a run
  of the workflow.
* ``--check-index-tmp``: Check index and temporary files (default is
  that only the output files are checked).
* ``--config-file``: Configuration file. If provided then the index,
  temporary and output directories specified in this file will be
  validated against those specified by ``--expected``. If not provided
  then the file :py:const:`riboviz.test.VIGNETTE_CONFIG` will be
  used. Sample names are extracted from
  :py:const:`riboviz.params.FQ_FILES`. If, instead,
  :py:const:`riboviz.params.MULTIPLEX_FQ_FILES` is provided then sample
  names are deduced from the names of folders in
  :py:const:`riboviz.params.OUTPUT_DIR` cross-referenced with the
  sample sheet file specified in
  :py:const:`riboviz.params.SAMPLE_SHEET`.
"""
import os.path
import pytest
import yaml
from riboviz import environment
from riboviz import fastq
from riboviz import params
from riboviz import sample_sheets
from riboviz import test

EXPECTED = "--expected"
""" Directory with expected data files command-line flag."""
SKIP_WORKFLOW = "--skip-workflow"
""" Do not run workflow command-line flag. """
CHECK_INDEX_TMP = "--check-index-tmp"
""" Check index and temporary files command-line flag. """
CONFIG_FILE = "--config-file"
""" Configuration file command-line flag. """


def pytest_addoption(parser):
    """
    pytest configuration hook.

    :param parser: command-line parser
    :type parser: _pytest.config.argparsing.Parser
    """
    parser.addoption(EXPECTED,
                     action="store",
                     required=True,
                     help="Directory with expected data files")
    parser.addoption(SKIP_WORKFLOW,
                     action="store_true",
                     required=False,
                     help="Do not run workflow")
    parser.addoption(CHECK_INDEX_TMP,
                     action="store_true",
                     required=False,
                     help="Check index and temporary files")
    parser.addoption(CONFIG_FILE,
                     action="store",
                     required=False,
                     help="Configuration file")


@pytest.fixture(scope="module")
def expected_fixture(request):
    """
    Gets value for ``--expected`` command-line option.

    :param request: request
    :type request: _pytest.fixtures.SubRequest
    :return: directory
    :rtype: str or unicode
    :raise AssertionError: if the option has a value that is \
    not a directory
    """
    expected_dir = request.config.getoption(EXPECTED)
    assert os.path.exists(expected_dir) and os.path.isdir(expected_dir),\
        "No such directory: %s" % expected_dir
    return expected_dir


@pytest.fixture(scope="module")
def skip_workflow_fixture(request):
    """
    Gets value for ``--skip-workflow`` command-line option.

    :param request: request
    :type request: _pytest.fixtures.SubRequest
    :return: flag
    :rtype: bool
    """
    return request.config.getoption(SKIP_WORKFLOW)


@pytest.fixture(scope="module")
def skip_index_tmp_fixture(request):
    """
    Gets value for `--check-index-tmp` command-line option. If
    ``False``, or undefined, invokes ``pytest.skip`` to skip
    test.

    :param request: request
    :type request: _pytest.fixtures.SubRequest
    :return: flag
    :rtype: bool
    """
    if not request.config.getoption(CHECK_INDEX_TMP):
        pytest.skip('Skipped index and temporary files tests')


@pytest.fixture(scope="module")
def config_fixture(request):
    """
    Gets value for ``--config-file`` command-line option.

    :param request: request
    :type request: _pytest.fixtures.SubRequest
    :return: configuration file
    :rtype: str or unicode
    """
    if request.config.getoption(CONFIG_FILE):
        config_file = request.config.getoption(CONFIG_FILE)
    else:
        config_file = test.VIGNETTE_CONFIG
    return config_file


def pytest_generate_tests(metafunc):
    """
    Parametrize tests using information within a configuration file.

    If :py:const:`CONFIG_FILE` has been provided then use this as a
    configuration file, else use
    :py:const:`riboviz.test.VIGNETTE_CONFIG`.

    Load configuration from file.

    Inspect each test fixture used by the test functions and \
    configure with values from the configuration:
    - ``sample``:
        - If :py:const:`riboviz.params.FQ_FILES` is provided then
          sample names are the keys from this value.
        - If :py:const:`riboviz.params.MULTIPLEX_FQ_FILES` then
          sample names are deduced from the names of folders in
          :py:const:`riboviz.params.OUTPUT_DIR` cross-referenced
          with the sample sheet file specified in
          :py:const:`riboviz.params.SAMPLE_SHEET`.
        - If sample name
          :py:const:`riboviz.test.VIGNETTE_MISSING_SAMPLE`
          is present, then it is removed from the sample names.
        - ``[]`` otherwise.
    - ``is_multiplexed``: list with ``False`` if
      :py:const:`riboviz.params.MULTIPLEX_FQ_FILES` defines one or
      more files, ``True`` otherwise.
    - ``multiplex_name``: list of multiplexed file name prefixed,
      without extensions, from
      :py:const:`riboviz.params.MULTIPLEX_FQ_FILES` if
      :py:const:`riboviz.params.MULTIPLEX_FQ_FILES` defines one or
      more files, ``[]`` otherwise.
    - ``index_prefix``: list with values of
      :py:const:`riboviz.params.ORF_INDEX_PREFIX` and
      :py:const:`riboviz.params.RRNA_INDEX_PREFIX`.
    - ``<param>``: where ``<param>`` is a key from
      :py:const:`riboviz.params.DEFAULT_VALUES` and the
       value is a list with either the value of the parameter from
      ``config``, if defined, or the default from
      :py:const:`riboviz.params.DEFAULT_VALUES`
      otherwise.

    :param metafunc: pytest test function inspection object
    :type metafunc: _pytest.python.Metafunc
    :raise AssertionError: if the configuration file does not \
    exist or is not a file
    """
    if metafunc.config.getoption(CONFIG_FILE):
        config_file = metafunc.config.getoption(CONFIG_FILE)
    else:
        config_file = test.VIGNETTE_CONFIG
    assert os.path.exists(config_file) and os.path.isfile(config_file),\
        "No such file: %s" % config_file
    with open(config_file, 'r') as f:
        config = yaml.load(f, yaml.SafeLoader)
    # Replace environment variable tokens with environment variables
    # in configuration parameter values that support environment
    # variables
    environment.apply_env_to_config(config)
    fixtures = {}
    for param, default in params.DEFAULT_VALUES.items():
        fixtures[param] = [default if param not in config
                           else config[param]]
    fixtures["index_prefix"] = [config[params.ORF_INDEX_PREFIX],
                                config[params.RRNA_INDEX_PREFIX]]
    fixtures["is_multiplexed"] = [
        params.MULTIPLEX_FQ_FILES in config
        and config[params.MULTIPLEX_FQ_FILES]]
    if "multiplex_name" in metafunc.fixturenames:
        multiplex_names = []
        if params.MULTIPLEX_FQ_FILES in config and config[params.MULTIPLEX_FQ_FILES]:
            multiplex_names = [
                os.path.splitext(fastq.strip_fastq_gz(file_name))[0]
                for file_name in config[params.MULTIPLEX_FQ_FILES]
            ]
        fixtures['multiplex_name'] = multiplex_names
    if "sample" in metafunc.fixturenames:
        samples = []
        if params.FQ_FILES in config and config[params.FQ_FILES]:
            samples = list(config[params.FQ_FILES].keys())
        elif params.MULTIPLEX_FQ_FILES in config and config[params.MULTIPLEX_FQ_FILES]:
            # Get samples from sample sheet.
            sample_sheet_file = os.path.join(
                config[params.INPUT_DIR],
                config[params.SAMPLE_SHEET])
            sample_sheet = sample_sheets.load_sample_sheet(
                sample_sheet_file)
            sample_sheet_samples = list(sample_sheet[sample_sheets.SAMPLE_ID])
            # Get folder/file names from output directory. These
            # include output folders for the samples which were
            # demultiplexed and other files.
            output_samples = os.listdir(config[params.OUTPUT_DIR])
            # Get names of samples for which output files exist.
            samples = list(set(sample_sheet_samples).intersection(
                set(output_samples)))
        if test.VIGNETTE_MISSING_SAMPLE in samples:
            samples.remove(test.VIGNETTE_MISSING_SAMPLE)
        fixtures["sample"] = samples
    for fixture, value in fixtures.items():
        if fixture in metafunc.fixturenames:
            metafunc.parametrize(fixture, value)

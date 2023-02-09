import pytest

import prefect.server


def test_import_orion_module():
    with pytest.warns(
        DeprecationWarning,
        match="The 'prefect.orion' module has been deprecated. It will not be available after Aug 2023. Use 'prefect.server' instead.",
    ):
        pass


def test_import_orion_submodule():
    with pytest.warns(
        DeprecationWarning,
        match="The 'prefect.orion' module has been deprecated. It will not be available after Aug 2023. Use 'prefect.server' instead.",
    ):
        import prefect.orion.schemas

    assert prefect.orion.schemas is prefect.server.schemas


def test_import_module_from_orion_module():
    # This does not throw a deprecation warning because we've already imported the
    # orion module in a prior test
    from prefect.orion import models

    assert models is prefect.server.models


def test_import_object_from_from_orion_submodule():
    with pytest.warns(
        DeprecationWarning,
        match="The 'prefect.orion' module has been deprecated. It will not be available after Aug 2023. Use 'prefect.server' instead.",
    ):
        from prefect.orion.schemas.states import State

    assert State is prefect.server.schemas.states.State

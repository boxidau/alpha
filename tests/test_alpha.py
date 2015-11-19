import os
from conftest import test_config


def test_enumerate_modules(create_file_structure_src, remove_network_alpha, monkeypatch):
    alpha = remove_network_alpha
    for path, config in alpha.enumerate_modules(create_file_structure_src):
        assert config == test_config
        assert path == os.path.join(create_file_structure_src, 'test-lambda')


def test_push_all_new(create_file_structure_src, remove_network_alpha):
    alpha = remove_network_alpha
    alpha.push_all(create_file_structure_src)

    assert alpha.lbd_fn_list == {'Functions':[]}
    assert alpha.iam.create_role.call_count == 1
    assert alpha.iam.get_role.call_count == 0
    assert alpha.lbd.create_function.call_count == 1
    assert alpha.iam.put_role_policy.call_count == 1
    assert alpha.lbd.list_functions.call_count == 1


def test_broken_configuration(create_broken_file_structure_src, remove_network_alpha):
    alpha = remove_network_alpha
    alpha.push_all(create_broken_file_structure_src)

    assert alpha.iam.create_role.call_count == 0
    assert alpha.lbd.create_function.call_count == 0
    assert alpha.iam.put_role_policy.call_count == 0
    assert alpha.lbd.list_functions.call_count == 0

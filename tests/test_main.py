from shellai import main


def test_get_args():
    _, args = main.get_args()
    assert not args.history_clear
    assert not args.record
    assert args.config == 'config.yaml'

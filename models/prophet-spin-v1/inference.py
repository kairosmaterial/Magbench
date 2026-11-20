"""Reference model adapter through the unchanged shared runner."""
from magbench.adapters import ProphetSpinV1


class Model(ProphetSpinV1):
    pass


if __name__ == '__main__':
    from magbench import adapters, cli
    adapters.ProphetSpinV1 = Model
    cli.main()

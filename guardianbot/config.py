import os
from dataclasses import dataclass
from typing import Optional, Union, get_args, get_origin


@dataclass(frozen=True)
class __Config:
    debug: bool
    token: str
    prefix: str
    guild_id: int
    data_dir: str

    git_commit: Optional[str]


def __get_value(field):
    if get_origin(field.type) is Union:  # Optional[X] is actually Union[X, None]
        args = get_args(field.type)
        assert len(args) == 2 and args[-1] is type(None)  # noqa: E721
        optional = True
        field_type = args[0]
    else:
        optional = False
        field_type = field.type

    env_name = f'DISCORD_{field.name.upper()}'
    try:
        val_str = os.environ[env_name]
        return field_type(val_str)
    except KeyError:
        if optional:
            return None
        raise RuntimeError(f'Environment variable \'{env_name}\' not set')
    except ValueError as e:
        raise ValueError(f'{e} (environment variable: \'{env_name}\')') from e


kv = {field.name: __get_value(field) for field in __Config.__dataclass_fields__.values()}  # type: ignore
Config = __Config(**kv)

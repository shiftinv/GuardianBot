import os
from dataclasses import dataclass, MISSING
from typing import Optional, Union, get_args, get_origin


@dataclass(frozen=True)
class __Config:
    debug: bool
    token: str
    prefix: str
    guild_id: int
    data_dir: str
    muted_role_id: Optional[int]
    git_commit: Optional[str]
    enable_owner_eval: bool = False


def __get_value(field):
    if get_origin(field.type) is Union:  # Optional[X] is actually Union[X, None]
        args = get_args(field.type)
        assert len(args) == 2 and args[-1] is type(None)  # noqa: E721
        is_optional = True
        field_type = args[0]
    else:
        is_optional = False
        field_type = field.type

    if get_origin(field_type) is list:
        is_list = True
        field_type = get_args(field_type)[0]
    else:
        is_list = False

    if field_type is bool:
        def to_bool(val: str) -> bool:
            val = val.lower()
            if val in ('1', 'true', 'yes'):
                return True
            elif val in ('0', 'false', 'no'):
                return False
            raise ValueError(f'Invalid bool value: \'{val}\'')
        field_type = to_bool

    env_name = f'DISCORD_{field.name.upper()}'
    try:
        val_str = os.environ[env_name]
        if is_list:
            return list(map(field_type, val_str.split(',')))
        else:
            return field_type(val_str)
    except KeyError:
        if is_optional:
            return None
        if field.default is not MISSING:
            return field.default
        raise RuntimeError(f'Environment variable \'{env_name}\' not set')
    except ValueError as e:
        raise ValueError(f'{e} (environment variable: \'{env_name}\')') from e


kv = {field.name: __get_value(field) for field in __Config.__dataclass_fields__.values()}  # type: ignore
Config = __Config(**kv)

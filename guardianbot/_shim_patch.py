import importlib
import importlib.metadata


# make sure shim module is installed
assert importlib.metadata.distribution('discord-disnake')

# emulate `import *`, but ignoring __all__
module = importlib.import_module('disnake.ext.tasks')
module_shim = importlib.import_module('discord.ext.tasks')
# copy locals
module_shim.__dict__.update(module.__dict__)

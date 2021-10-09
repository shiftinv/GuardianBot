# GuardianBot

Yet another Discord anti-spam bot, with keyword blocklists and DNS/IP-based link filtering.


## Installation

1. Copy `docker-compose.yml.skel` to `docker-compose.yml`, add the token, guild ID, and muted role ID (see below)
2. Create the data directory (`_data` by default, see `docker-compose.yml`), and update the permissions (`chmod 777 _data` or `chown 1000:1000 _data`)
3. Build + Run: `make && docker-compose up`


## Configuration

1. Set up a role to assign to muted users, below the bot's role but above `@everyone`
2. Update all (public) channels and deny this new role the `Send Messages` permission
    - this can get tedious pretty quickly, but the bot (currently) can't do that on its own
3. Update the bot's configuration:
    - Set the channel to send reports to: `?filter config report_channel <channel_id>`
    - Set the mute duration: `?filter config mute_minutes 1337`
    - Add roles to be excluded from filter: `?filter config unfiltered_roles <role_id>`
        - an excluded role may be included in filters again by running the same command again


## Usage

(see [guardianbot/cogs/filter.py](./guardianbot/cogs/filter.py) for reference)

There are three types of filter lists, which are checked in order:
- `strings`, contains keywords which are matched literally (case sensitive)
- `regex`, contains regular expressions to filter with
- `ips`, contains IPs or CIDRs (e.g. `127.0.0.0/8`) of domains to filter

Commands for managing these lists:
- `?filter add <list> <keyword/ip>`
- `?filter remove <list> <keyword/ip>`
- `?filter list <list> [raw]`

<br>

The [core](./guardianbot/cogs/core.py) cog contains a few general-purpose commands:
- `?info` (displays version info, uptime, ping)
- `?say <channel> <message>` (self-explanatory)
- `?shutdown`/`?restart` (shuts down the bot, immediately restarting again by default as specified in `docker-compose.yml`).


## Notes
- A user must either be the bot owner or have the `Manage Messages` permission to be able to issue commands (see [`__main__.global_command_filter`](./guardianbot/__main__.py))
- Filter automatically excludes commands and other bots, in addition to the specified roles
- This bot uses [discord.py](https://github.com/Rapptz/discord.py) v2/master, not the latest release (v1.7.3 at the time of writing), so be prepared for bugs/stability issues
- If no muted role is configured, the bot will only delete matching messages and not assign any role

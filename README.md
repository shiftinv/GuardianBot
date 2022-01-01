# GuardianBot

Yet another Discord anti-spam bot, with keyword/regex blocklists and DNS/IP-based link filtering.


## Installation

1. Create a bot in the developer portal, enable all privileged intents, and copy the token as usual
2. Invite the bot to a server, with the `bot` and `applications.commands` scopes, and with at least the following permissions:  
   `Manage Roles`, `View Channels`, `Moderate Members/Time Out Members`, `Send Messages`, and `Manage Messages`
2. Copy `docker-compose.yml.skel` to `docker-compose.yml`, and fill in the environment variables marked with `<EMPTY>`
    - `MOD_ROLE_IDS` is primarily cosmetic and only used to restrict slash commands to specific roles. Any user will still always require the `Manage Messages` permission for commands, regardless of this value
3. Create the data directory (`_data` by default, see `docker-compose.yml`), and update the permissions (`chmod 777 _data` or `chown 1000:1000 _data`)
4. Build + Run: `make && docker-compose up`


## Configuration

1. Temporary mutes (up to 28 days) use Discord's builtin timeout feature; permanent mutes require a separate role:
    1. Set up a role to assign to muted users, below the bot's role but above `@everyone`
    2. Update all (public) channels and deny this new role the `Send Messages` permission
        - this can get tedious pretty quickly, but the bot (currently) can't do that on its own
3. Update the bot's configuration:
    - Set the channel to send reports to: `?filter config report_channel <channel_id>`
    - Set the mute duration: `?filter config mute_minutes 10`
    - Add roles to be excluded from filter: `?filter config unfiltered_roles <role_id>`
        - an excluded role may be included in filters again by running the same command again
    - Optionally, for the spam filter (also see below):
        - Change the interval length: `?filter config spam_interval_sec 15`
        - Change the number of required repetitions of a message within the interval for it to be considered spam: `?filter config spam_repeat_count 2`


## Usage

**Note: all commands are also available as prefix commands, i.e. using `?` instead of `/`.**

The [filter](./guardianbot/cogs/filter.py) cog handles four types of filter lists, which are checked in order:
- `strings`, contains keywords which are matched literally (case sensitive)
- `regex`, contains regular expressions to filter with
- `bad_domains`, which is automatically updated from Discord's bad-domains hash list, and cannot be modified manually
- `spam_regex`, contains regular expressions for messages that will be taken into consideration by the spam filter
- `ips`, contains IPs or CIDRs (e.g. `127.0.0.0/8`) of domains to filter

The `allowed_hosts` list can be used to explicitly allow specific domains/hostnames.

Commands for managing lists:
- `/filter add <list> <keyword/ip>`
- `/filter remove <list> <keyword/ip>`
- `/filter list <list> [raw]`

Additionally, there are `/mute <user> <duration>` / `/unmute <user>` commands, and a `/muted` command to list currently muted users and the expiry.

<br>

The [core](./guardianbot/cogs/core.py) cog contains a few general-purpose and utility commands.


### Spam Filter
The spam filter only takes messages into account that match one of the regular expressions in the `spam_regex` list. If `[spam_repeat_count]` *identical* messages by the same user are observed within `[spam_interval_sec]`, they are considered spam, get removed, and the user gets muted as usual.


---
## Notes

- A user must either be the bot owner or have the `Manage Messages` permission to be able to issue most commands
- Filter automatically excludes commands and other bots, in addition to the specified roles

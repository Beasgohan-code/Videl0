# Registered command reference

Generated from the bot's registered command manifest and installed handlers.
This documents navigation and source coverage, not verified live Telegram behavior.
Aliases are listed separately; permissions remain enforced by the referenced handler.
Owner operations are hidden from public `/commands` results.

159 distinct command names.

## Music & playlists

| Command | Context | Handler |
|---|---|---|
| `/autoplay` | group | `videl/modules/autoplay.py::autoplay_cmd` |
| `/bass` | group | `videl/modules/effects.py::bass_cmd` |
| `/bassoff` | group | `videl/modules/effects.py::bassoff_cmd` |
| `/channelplay` | group | `videl/modules/cplay.py::channelplay_cmd` |
| `/clear` | group | `videl/app/music.py::control` |
| `/cplay` | group | `videl/modules/cplay.py::cplay_handler` |
| `/cvplay` | group | `videl/modules/cplay.py::cplay_handler` |
| `/deleteplaylist` | chat | `videl/modules/playlist.py::delete_playlist_cmd` |
| `/download` | group | `videl/modules/downloader.py::download_cmd` |
| `/effectoff` | group | `videl/modules/effects.py::effectoff_cmd` |
| `/effecton` | group | `videl/modules/effects.py::effecton_cmd` |
| `/effects` | group | `videl/modules/effects.py::effects_status_cmd` |
| `/end` | group | `videl/app/music.py::control` |
| `/loop` | group | `videl/app/music.py::control` |
| `/lyrics` | chat | `videl/modules/lyrics.py::lyrics_cmd` |
| `/pause` | group | `videl/app/music.py::control` |
| `/play` | group | `videl/modules/play.py::play_handler` |
| `/playlist` | group | `videl/modules/playlist.py::load_playlist_cmd` |
| `/playlists` | chat | `videl/modules/playlist.py::list_playlists_cmd` |
| `/q` | group | `videl/app/music.py::view_queue` |
| `/queue` | group | `videl/app/music.py::view_queue` |
| `/replay` | group | `videl/app/music.py::control` |
| `/resetplayer` | group | `videl/app/music.py::control` |
| `/resume` | group | `videl/app/music.py::control` |
| `/saveplaylist` | group | `videl/modules/playlist.py::save_playlist_cmd` |
| `/seek` | group | `videl/modules/seek.py::seek_cmd` |
| `/seekback` | group | `videl/modules/seek.py::seekback_cmd` |
| `/shuffle` | group | `videl/app/music.py::control` |
| `/skip` | group | `videl/app/music.py::control` |
| `/song` | group | `videl/modules/downloader.py::song_cmd` |
| `/speed` | group | `videl/modules/effects.py::speed_cmd` |
| `/speedreset` | group | `videl/modules/effects.py::speedreset_cmd` |
| `/stop` | group | `videl/app/music.py::control` |
| `/voteskip` | group | `videl/modules/smartqueue.py::set_voteskip_cmd` |
| `/vplay` | group | `videl/modules/play.py::play_handler` |
| `/vsong` | group | `videl/modules/downloader.py::vsong_cmd` |

## Groups & protection

| Command | Context | Handler |
|---|---|---|
| `/addblacklist` | group | `videl/modules/blocklist.py::addbl_cmd` |
| `/addblsticker` | group | `videl/modules/blocklist.py::add_bl_sticker` |
| `/admins` | chat | `videl/app/moderation.py::admins` |
| `/antispam` | group | `videl/app/locks.py::antispam` |
| `/approval` | group | `videl/modules/approve.py::approval_info` |
| `/approve` | group | `videl/modules/approve.py::approve_cmd` |
| `/approved` | group | `videl/modules/approve.py::approved_list` |
| `/ban` | group | `videl/app/moderation.py::moderate` |
| `/banlist` | group | `videl/app/moderation.py::ban_list` |
| `/blacklist` | group | `videl/modules/blocklist.py::listbl_cmd` |
| `/blacklistmode` | group | `videl/modules/blocklist.py::blmode_cmd` |
| `/blstickers` | group | `videl/modules/blocklist.py::list_bl_stickers_cmd` |
| `/chatfed` | group | `videl/modules/federation.py::joinfed_cmd` |
| `/cleanup` | group | `videl/app/group.py::purge` |
| `/clearrules` | group | `videl/app/welcome.py::clear_rules` |
| `/clearwarns` | group | `videl/app/moderation.py::clear_warnings` |
| `/dban` | group | `videl/app/moderation.py::moderate` |
| `/delblacklist` | group | `videl/modules/blocklist.py::delbl_cmd` |
| `/delblsticker` | group | `videl/modules/blocklist.py::del_bl_sticker` |
| `/delfed` | chat | `videl/modules/federation.py::delfed_cmd` |
| `/delnote` | group | `videl/app/notes.py::delete_note` |
| `/demote` | group | `videl/app/moderation.py::demote` |
| `/dkick` | group | `videl/app/moderation.py::moderate` |
| `/dwarn` | group | `videl/app/moderation.py::warn` |
| `/faddadmin` | chat | `videl/modules/federation.py::fpromote_cmd` |
| `/fban` | chat | `videl/modules/federation.py::fban_cmd` |
| `/fdemote` | chat | `videl/modules/federation.py::fdemote_cmd` |
| `/fedbanlist` | chat | `videl/modules/federation.py::fedbanlist_cmd` |
| `/fedchats` | chat | `videl/modules/federation.py::fedchats_cmd` |
| `/fedinfo` | chat | `videl/modules/federation.py::fedinfo_cmd` |
| `/fedstat` | chat | `videl/modules/federation.py::fedinfo_cmd` |
| `/filter` | group | `videl/app/notes.py::add_filter` |
| `/filters` | group | `videl/app/notes.py::list_filters` |
| `/fpromote` | chat | `videl/modules/federation.py::fpromote_cmd` |
| `/fremadmin` | chat | `videl/modules/federation.py::fdemote_cmd` |
| `/get` | group | `videl/app/notes.py::get` |
| `/goodbye` | group | `videl/app/welcome.py::toggle_goodbye` |
| `/greetings` | group | `videl/app/welcome.py::greeting_status` |
| `/group` | group | `videl/modules/group_manager.py::group_command` |
| `/groupview` | group | `videl/app/group_view.py::recording` |
| `/invite` | group | `videl/app/group.py::invite` |
| `/joinfed` | group | `videl/modules/federation.py::joinfed_cmd` |
| `/kick` | group | `videl/app/moderation.py::moderate` |
| `/leavefed` | group | `videl/modules/federation.py::leavefed_cmd` |
| `/lock` | group | `videl/app/locks.py::lock` |
| `/locks` | group | `videl/app/locks.py::locks` |
| `/mute` | group | `videl/app/moderation.py::moderate` |
| `/myfeds` | chat | `videl/modules/federation.py::myfeds_cmd` |
| `/newfed` | group | `videl/modules/federation.py::newfed_cmd` |
| `/notes` | group | `videl/app/notes.py::list_notes` |
| `/permissions` | group | `videl/modules/group_manager.py::permission_command` |
| `/pin` | group | `videl/app/group.py::pin` |
| `/promote` | group | `videl/app/moderation.py::promote` |
| `/purge` | group | `videl/app/group.py::purge` |
| `/report` | group | `videl/modules/group_manager.py::report_command` |
| `/rmblacklist` | group | `videl/modules/blocklist.py::delbl_cmd` |
| `/rules` | group | `videl/app/welcome.py::rules` |
| `/save` | group | `videl/app/notes.py::save` |
| `/setcaptcha` | group | `videl/app/welcome.py::toggle_captcha` |
| `/setgoodbye` | group | `videl/app/welcome.py::set_goodbye` |
| `/setrules` | group | `videl/app/welcome.py::set_rules` |
| `/setup` | group | `videl/modules/group_manager.py::group_command` |
| `/setwarnlimit` | group | `videl/app/moderation.py::set_warn_limit` |
| `/setwelcome` | group | `videl/app/welcome.py::set_welcome` |
| `/slowmode` | group | `videl/app/group.py::slowmode` |
| `/stopfilter` | group | `videl/app/notes.py::remove_filter` |
| `/tban` | group | `videl/app/moderation.py::moderate` |
| `/tmute` | group | `videl/app/moderation.py::moderate` |
| `/unapprove` | group | `videl/modules/approve.py::unapprove_cmd` |
| `/unban` | group | `videl/app/moderation.py::moderate` |
| `/unfban` | chat | `videl/modules/federation.py::unfban_cmd` |
| `/unlock` | group | `videl/app/locks.py::unlock` |
| `/unmute` | group | `videl/app/moderation.py::moderate` |
| `/unpin` | group | `videl/app/group.py::pin` |
| `/unpinall` | group | `videl/app/group.py::pin` |
| `/unwarn` | group | `videl/app/moderation.py::unwarn` |
| `/warn` | group | `videl/app/moderation.py::warn` |
| `/warnings` | chat | `videl/app/moderation.py::warnings` |
| `/welcome` | group | `videl/app/welcome.py::toggle_welcome` |

## Telegram tools

| Command | Context | Handler |
|---|---|---|
| `/about` | chat | `videl/app/start.py::about` |
| `/afk` | chat | `videl/app/afk.py::afk` |
| `/afklist` | group | `videl/app/afk.py::afk_list` |
| `/back` | chat | `videl/app/afk.py::back` |
| `/commands` | chat | `videl/app/help.py::directory_command` |
| `/copy` | chat | `videl/modules/api_tools.py::copy_command` |
| `/font` | chat | `videl/app/fun.py::font` |
| `/forget` | chat | `videl/app/reminder.py::forget` |
| `/help` | chat | `videl/app/help.py::help_command` |
| `/hug` | chat | `videl/app/fun.py::hug` |
| `/id` | chat | `videl/app/tools.py::identifiers` |
| `/inbox` | chat | `videl/app/group_view.py::private_recording` |
| `/kang` | chat | `videl/app/stickers.py::kang` |
| `/kiss` | chat | `videl/app/fun.py::kiss` |
| `/modernhelp` | chat | `videl/modules/api_tools.py::modern_help` |
| `/ping` | chat | `videl/app/tools.py::ping` |
| `/poll` | chat | `videl/app/group.py::poll` |
| `/pollstop` | chat | `videl/modules/api_tools.py::stop_poll_command` |
| `/quiz` | chat | `videl/app/group.py::poll` |
| `/react` | chat | `videl/modules/api_tools.py::react_command` |
| `/remind` | chat | `videl/app/reminder.py::remind` |
| `/reminders` | chat | `videl/app/reminder.py::reminders` |
| `/repo` | chat | `videl/app/tools.py::source` |
| `/start` | chat | `videl/app/start.py::start` |
| `/stats` | chat | `videl/app/group.py::stats` |
| `/stickerid` | chat | `videl/app/group.py::sticker_id` |
| `/topicclose` | chat | `videl/modules/api_tools.py::topic_command` |
| `/topicnew` | chat | `videl/modules/api_tools.py::topic_command` |
| `/topicopen` | chat | `videl/modules/api_tools.py::topic_command` |
| `/topicrename` | chat | `videl/modules/api_tools.py::topic_command` |
| `/whois` | chat | `videl/app/tools.py::whois` |

## Owner operations

| Command | Context | Handler |
|---|---|---|
| `/active` | private | `videl/modules/owner_utils.py::active` |
| `/apiinfo` | private | `videl/modules/api_tools.py::api_info` |
| `/blocklist` | chat | `videl/modules/block.py::blocklist_cmd` |
| `/broadcast` | chat | `videl/modules/broadcast.py::broadcast_cmd` |
| `/dbcleanup` | private | `videl/modules/misc.py::cleanup_cmd` |
| `/emojiinfo` | private | `videl/modules/api_tools.py::emoji_info` |
| `/gblock` | chat | `videl/modules/block.py::gblock_cmd` |
| `/gcast` | chat | `videl/modules/broadcast.py::broadcast_cmd` |
| `/gunblock` | chat | `videl/modules/block.py::gunblock_cmd` |
| `/sysinfo` | private | `videl/modules/owner_utils.py::system_info` |
| `/ublock` | chat | `videl/modules/block.py::ublock_cmd` |
| `/uunblock` | chat | `videl/modules/block.py::uunblock_cmd` |
| `/watchdog` | private | `videl/modules/misc.py::watchdog_cmd` |

## UI and transport exceptions

Authored command feedback uses the vendored Badmunda05 Richgram helpers and native Kurigram keyboards.
Telegram polls, media/file delivery, forwards/copies, user-authored saved notes, filters and welcome templates
retain their native Telegram transport. They are not wrapped into decorative rich cards or rewritten.
Callback answers remain native short notifications. This is intentional, not an unimplemented rich UI path.
No automatic resend is allowed when a send times out or its outcome is unknown.

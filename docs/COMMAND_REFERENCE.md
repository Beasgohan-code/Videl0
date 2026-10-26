# Registered command reference

Generated from the bot's registered command manifest and installed handlers.
This documents navigation and source coverage, not verified live Telegram behavior.
Aliases are listed separately; permissions remain enforced by the referenced handler.
Owner operations are hidden from public `/commands` results.

168 distinct command names.

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
| `/admins` | chat | `videl/plugins/moderation.py::admins` |
| `/antispam` | group | `videl/plugins/locks.py::antispam` |
| `/approval` | group | `videl/modules/approve.py::approval_info` |
| `/approve` | group | `videl/modules/approve.py::approve_cmd` |
| `/approved` | group | `videl/modules/approve.py::approved_list` |
| `/ban` | group | `videl/plugins/moderation.py::moderate` |
| `/banlist` | group | `videl/plugins/moderation.py::ban_list` |
| `/blacklist` | group | `videl/modules/blocklist.py::listbl_cmd` |
| `/blacklistmode` | group | `videl/modules/blocklist.py::blmode_cmd` |
| `/blstickers` | group | `videl/modules/blocklist.py::list_bl_stickers_cmd` |
| `/chatfed` | group | `videl/modules/federation.py::joinfed_cmd` |
| `/cleanup` | group | `videl/plugins/group.py::purge` |
| `/clearrules` | group | `videl/plugins/welcome.py::clear_rules` |
| `/clearwarns` | group | `videl/plugins/moderation.py::clear_warnings` |
| `/dban` | group | `videl/plugins/moderation.py::moderate` |
| `/delblacklist` | group | `videl/modules/blocklist.py::delbl_cmd` |
| `/delblsticker` | group | `videl/modules/blocklist.py::del_bl_sticker` |
| `/delfed` | chat | `videl/modules/federation.py::delfed_cmd` |
| `/delnote` | group | `videl/plugins/notes.py::delete_note` |
| `/delphoto` | group | `videl/plugins/group.py::delete_photo` |
| `/demote` | group | `videl/plugins/moderation.py::demote` |
| `/dkick` | group | `videl/plugins/moderation.py::moderate` |
| `/dwarn` | group | `videl/plugins/moderation.py::warn` |
| `/faddadmin` | chat | `videl/modules/federation.py::fpromote_cmd` |
| `/fban` | chat | `videl/modules/federation.py::fban_cmd` |
| `/fdemote` | chat | `videl/modules/federation.py::fdemote_cmd` |
| `/fedbanlist` | chat | `videl/modules/federation.py::fedbanlist_cmd` |
| `/fedchats` | chat | `videl/modules/federation.py::fedchats_cmd` |
| `/fedinfo` | chat | `videl/modules/federation.py::fedinfo_cmd` |
| `/fedstat` | chat | `videl/modules/federation.py::fedinfo_cmd` |
| `/filter` | group | `videl/plugins/notes.py::add_filter` |
| `/filters` | group | `videl/plugins/notes.py::list_filters` |
| `/fpromote` | chat | `videl/modules/federation.py::fpromote_cmd` |
| `/fremadmin` | chat | `videl/modules/federation.py::fdemote_cmd` |
| `/get` | group | `videl/plugins/notes.py::get` |
| `/goodbye` | group | `videl/plugins/welcome.py::toggle_goodbye` |
| `/greetings` | group | `videl/plugins/welcome.py::greeting_status` |
| `/group` | group | `videl/modules/group_manager.py::group_command` |
| `/groupview` | group | `videl/app/group_view.py::recording` |
| `/invite` | group | `videl/plugins/group.py::invite` |
| `/joinfed` | group | `videl/modules/federation.py::joinfed_cmd` |
| `/kick` | group | `videl/plugins/moderation.py::moderate` |
| `/leavefed` | group | `videl/modules/federation.py::leavefed_cmd` |
| `/lock` | group | `videl/plugins/locks.py::lock` |
| `/locks` | group | `videl/plugins/locks.py::locks` |
| `/mute` | group | `videl/plugins/moderation.py::moderate` |
| `/myfeds` | chat | `videl/modules/federation.py::myfeds_cmd` |
| `/newfed` | group | `videl/modules/federation.py::newfed_cmd` |
| `/notes` | group | `videl/plugins/notes.py::list_notes` |
| `/permissions` | group | `videl/modules/group_manager.py::permission_command` |
| `/pin` | group | `videl/plugins/group.py::pin` |
| `/promote` | group | `videl/plugins/moderation.py::promote` |
| `/purge` | group | `videl/plugins/group.py::purge` |
| `/report` | group | `videl/modules/group_manager.py::report_command` |
| `/rmblacklist` | group | `videl/modules/blocklist.py::delbl_cmd` |
| `/rules` | group | `videl/plugins/welcome.py::rules` |
| `/save` | group | `videl/plugins/notes.py::save` |
| `/setcaptcha` | group | `videl/plugins/welcome.py::toggle_captcha` |
| `/setdescription` | group | `videl/plugins/group.py::set_description` |
| `/setgoodbye` | group | `videl/plugins/welcome.py::set_goodbye` |
| `/setphoto` | group | `videl/plugins/group.py::set_photo` |
| `/setrules` | group | `videl/plugins/welcome.py::set_rules` |
| `/settitle` | group | `videl/plugins/group.py::set_title` |
| `/setup` | group | `videl/plugins/setup.py::setup` |
| `/setwarnlimit` | group | `videl/plugins/moderation.py::set_warn_limit` |
| `/setwelcome` | group | `videl/plugins/welcome.py::set_welcome` |
| `/slowmode` | group | `videl/plugins/group.py::slowmode` |
| `/stopfilter` | group | `videl/plugins/notes.py::remove_filter` |
| `/tagall` | group | `videl/plugins/group.py::tagall` |
| `/tban` | group | `videl/plugins/moderation.py::moderate` |
| `/tmute` | group | `videl/plugins/moderation.py::moderate` |
| `/unapprove` | group | `videl/modules/approve.py::unapprove_cmd` |
| `/unban` | group | `videl/plugins/moderation.py::moderate` |
| `/unfban` | chat | `videl/modules/federation.py::unfban_cmd` |
| `/unlock` | group | `videl/plugins/locks.py::unlock` |
| `/unmute` | group | `videl/plugins/moderation.py::moderate` |
| `/unpin` | group | `videl/plugins/group.py::pin` |
| `/unpinall` | group | `videl/plugins/group.py::pin` |
| `/unwarn` | group | `videl/plugins/moderation.py::unwarn` |
| `/warn` | group | `videl/plugins/moderation.py::warn` |
| `/warnings` | chat | `videl/plugins/moderation.py::warnings` |
| `/welcome` | group | `videl/plugins/welcome.py::toggle_welcome` |

## Telegram tools

| Command | Context | Handler |
|---|---|---|
| `/about` | chat | `videl/plugins/start.py::about` |
| `/afk` | chat | `videl/plugins/afk.py::afk` |
| `/afklist` | group | `videl/plugins/afk.py::afk_list` |
| `/back` | chat | `videl/plugins/afk.py::back` |
| `/commands` | chat | `videl/plugins/help.py::directory_command` |
| `/copy` | chat | `videl/modules/api_tools.py::copy_command` |
| `/dance` | chat | `videl/plugins/fun.py::dance` |
| `/font` | chat | `videl/plugins/fun.py::font` |
| `/forget` | chat | `videl/plugins/reminder.py::forget` |
| `/help` | chat | `videl/plugins/help.py::help_command` |
| `/highfive` | chat | `videl/plugins/fun.py::highfive` |
| `/hug` | chat | `videl/plugins/fun.py::hug` |
| `/id` | chat | `videl/plugins/tools.py::identifiers` |
| `/inbox` | chat | `videl/app/group_view.py::private_recording` |
| `/kang` | chat | `videl/plugins/stickers.py::kang` |
| `/kiss` | chat | `videl/plugins/fun.py::kiss` |
| `/like` | chat | `videl/plugins/fun.py::like` |
| `/modernhelp` | chat | `videl/modules/api_tools.py::modern_help` |
| `/ping` | chat | `videl/plugins/tools.py::ping` |
| `/poll` | chat | `videl/plugins/group.py::poll` |
| `/pollstop` | chat | `videl/modules/api_tools.py::stop_poll_command` |
| `/quiz` | chat | `videl/plugins/group.py::poll` |
| `/react` | chat | `videl/modules/api_tools.py::react_command` |
| `/remind` | chat | `videl/plugins/reminder.py::remind` |
| `/reminders` | chat | `videl/plugins/reminder.py::reminders` |
| `/repo` | chat | `videl/plugins/tools.py::source` |
| `/start` | chat | `videl/plugins/start.py::start` |
| `/stats` | chat | `videl/plugins/group.py::stats` |
| `/stickerid` | chat | `videl/plugins/group.py::sticker_id` |
| `/topicclose` | chat | `videl/modules/api_tools.py::topic_command` |
| `/topicnew` | chat | `videl/modules/api_tools.py::topic_command` |
| `/topicopen` | chat | `videl/modules/api_tools.py::topic_command` |
| `/topicrename` | chat | `videl/modules/api_tools.py::topic_command` |
| `/wave` | chat | `videl/plugins/fun.py::wave` |
| `/whois` | chat | `videl/plugins/tools.py::whois` |

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

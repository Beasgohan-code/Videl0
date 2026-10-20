# Registered command reference

Generated from registered command and regex handlers plus the two enabled plugins.
This documents navigation and source coverage, not verified live Telegram behavior.
Aliases are listed separately; permissions remain enforced by the referenced handler.
Owner operations are hidden from public `/commands` results.

150 distinct command names.

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
| `/admins` | group | `videl/modules/management_core.py::getadmins_cmd` |
| `/approval` | group | `videl/modules/approve.py::approval_info` |
| `/approve` | group | `videl/modules/approve.py::approve_cmd` |
| `/approved` | group | `videl/modules/approve.py::approved_list` |
| `/ban` | group | `videl/app/moderation.py::moderate` |
| `/banlist` | group | `videl/modules/management_core.py::banlist_cmd` |
| `/blacklist` | group | `videl/modules/blocklist.py::listbl_cmd` |
| `/blacklistmode` | group | `videl/modules/blocklist.py::blmode_cmd` |
| `/blstickers` | group | `videl/modules/blocklist.py::list_bl_stickers_cmd` |
| `/chatfed` | group | `videl/modules/federation.py::joinfed_cmd` |
| `/cleanup` | group | `videl/modules/management_core.py::purge_cmd` |
| `/clearrules` | group | `videl/modules/management_core.py::clearrules_cmd` |
| `/clearwarns` | group | `videl/modules/management_core.py::clearwarns_cmd` |
| `/dban` | group | `videl/app/moderation.py::moderate` |
| `/delblacklist` | group | `videl/modules/blocklist.py::delbl_cmd` |
| `/delblsticker` | group | `videl/modules/blocklist.py::del_bl_sticker` |
| `/delfed` | chat | `videl/modules/federation.py::delfed_cmd` |
| `/delnote` | group | `videl/modules/management_core.py::delnote_cmd` |
| `/demote` | group | `videl/modules/management_core.py::demote_cmd` |
| `/dkick` | group | `videl/app/moderation.py::moderate` |
| `/dwarn` | group | `videl/modules/management_core.py::warn_cmd` |
| `/faddadmin` | chat | `videl/modules/federation.py::fpromote_cmd` |
| `/fban` | chat | `videl/modules/federation.py::fban_cmd` |
| `/fdemote` | chat | `videl/modules/federation.py::fdemote_cmd` |
| `/fedbanlist` | chat | `videl/modules/federation.py::fedbanlist_cmd` |
| `/fedchats` | chat | `videl/modules/federation.py::fedchats_cmd` |
| `/fedinfo` | chat | `videl/modules/federation.py::fedinfo_cmd` |
| `/fedstat` | chat | `videl/modules/federation.py::fedinfo_cmd` |
| `/filter` | group | `videl/modules/management_core.py::filter_add_cmd` |
| `/filters` | group | `videl/modules/management_core.py::filters_list_cmd` |
| `/fpromote` | chat | `videl/modules/federation.py::fpromote_cmd` |
| `/fremadmin` | chat | `videl/modules/federation.py::fdemote_cmd` |
| `/get` | group | `videl/modules/management_core.py::get_note_cmd` |
| `/getadmins` | group | `videl/modules/management_core.py::getadmins_cmd` |
| `/group` | group | `videl/modules/group_manager.py::group_command` |
| `/groupview` | group | `videl/app/group_view.py::recording` |
| `/invite` | group | `videl/modules/group_manager.py::invite_command` |
| `/joinfed` | group | `videl/modules/federation.py::joinfed_cmd` |
| `/kick` | group | `videl/app/moderation.py::moderate` |
| `/leavefed` | group | `videl/modules/federation.py::leavefed_cmd` |
| `/lock` | group | `videl/modules/management_core.py::lock_cmd` |
| `/locks` | group | `videl/modules/management_core.py::locks_cmd` |
| `/mute` | group | `videl/app/moderation.py::moderate` |
| `/myfeds` | chat | `videl/modules/federation.py::myfeds_cmd` |
| `/newfed` | group | `videl/modules/federation.py::newfed_cmd` |
| `/notes` | group | `videl/modules/management_core.py::notes_list_cmd` |
| `/permissions` | group | `videl/modules/group_manager.py::permission_command` |
| `/pin` | group | `videl/modules/management_core.py::pin_cmds` |
| `/poll` | chat | `videl/modules/management_core.py::poll_cmd` |
| `/promote` | group | `videl/modules/management_core.py::promote_cmd` |
| `/purge` | group | `videl/modules/management_core.py::purge_cmd` |
| `/quiz` | chat | `videl/modules/management_core.py::poll_cmd` |
| `/report` | group | `videl/modules/group_manager.py::report_command` |
| `/resetwarns` | group | `videl/modules/management_core.py::clearwarns_cmd` |
| `/rmblacklist` | group | `videl/modules/blocklist.py::delbl_cmd` |
| `/rmwarn` | group | `videl/modules/management_core.py::unwarn_cmd` |
| `/rules` | group | `videl/modules/management_core.py::rules_cmd` |
| `/save` | group | `videl/modules/management_core.py::save_note_cmd` |
| `/setcaptcha` | group | `videl/modules/management_core.py::setcaptcha_cmd` |
| `/setrules` | group | `videl/modules/management_core.py::setrules_cmd` |
| `/setup` | group | `videl/modules/group_manager.py::group_command` |
| `/setwarnlimit` | group | `videl/modules/management_core.py::setwarnlimit_cmd` |
| `/setwelcome` | group | `videl/modules/management_core.py::setwelcome_cmd` |
| `/slowmode` | group | `videl/modules/management_core.py::slowmode_cmd` |
| `/stats` | chat | `videl/modules/management_core.py::stats_cmd` |
| `/stickerid` | chat | `videl/modules/management_core.py::stickerid_cmd` |
| `/stopfilter` | group | `videl/modules/management_core.py::filter_stop_cmd` |
| `/tban` | group | `videl/app/moderation.py::moderate` |
| `/tmute` | group | `videl/app/moderation.py::moderate` |
| `/unapprove` | group | `videl/modules/approve.py::unapprove_cmd` |
| `/unban` | group | `videl/app/moderation.py::moderate` |
| `/unfban` | chat | `videl/modules/federation.py::unfban_cmd` |
| `/unlock` | group | `videl/modules/management_core.py::unlock_cmd` |
| `/unmute` | group | `videl/app/moderation.py::moderate` |
| `/unpin` | group | `videl/modules/management_core.py::pin_cmds` |
| `/unpinall` | group | `videl/modules/management_core.py::pin_cmds` |
| `/unwarn` | group | `videl/modules/management_core.py::unwarn_cmd` |
| `/warn` | group | `videl/modules/management_core.py::warn_cmd` |
| `/warnings` | group | `videl/modules/management_core.py::warnings_cmd` |
| `/warns` | group | `videl/modules/management_core.py::warnings_cmd` |
| `/welcome` | group | `videl/modules/management_core.py::welcome_toggle_cmd` |
| `/whois` | chat | `videl/modules/management_core.py::whois_cmd` |

## Telegram tools

| Command | Context | Handler |
|---|---|---|
| `/afk` | chat | `videl/plugins/afk.py::afk_command` |
| `/commands` | chat | `videl/app/general.py::directory_command` |
| `/copy` | chat | `videl/modules/api_tools.py::copy_command` |
| `/help` | chat | `videl/app/general.py::help_command` |
| `/id` | chat | `videl/app/general.py::identifiers` |
| `/inbox` | chat | `videl/app/group_view.py::private_recording` |
| `/modernhelp` | chat | `videl/modules/api_tools.py::modern_help` |
| `/ping` | chat | `videl/app/general.py::ping` |
| `/pollstop` | chat | `videl/modules/api_tools.py::stop_poll_command` |
| `/react` | chat | `videl/modules/api_tools.py::react_command` |
| `/remind` | chat | `videl/plugins/reminder.py::reminder_command` |
| `/repo` | chat | `videl/app/general.py::source` |
| `/start` | chat | `videl/app/general.py::start` |
| `/topicclose` | chat | `videl/modules/api_tools.py::topic_command` |
| `/topicnew` | chat | `videl/modules/api_tools.py::topic_command` |
| `/topicopen` | chat | `videl/modules/api_tools.py::topic_command` |
| `/topicrename` | chat | `videl/modules/api_tools.py::topic_command` |

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

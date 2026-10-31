# Registered command reference

Generated from the bot's registered command manifest and installed handlers.
This documents navigation and source coverage, not verified live Telegram behavior.
Aliases are listed separately; permissions remain enforced by the referenced handler.
Owner operations are hidden from public `/commands` results.

203 distinct command names.

## Music & playlists

| Command | Context | Handler |
|---|---|---|
| `/autoplay` | group | `videl/modules/autoplay.py::autoplay_cmd` |
| `/bass` | group | `videl/modules/effects.py::bass_cmd` |
| `/bassoff` | group | `videl/modules/effects.py::bassoff_cmd` |
| `/channelplay` | group | `videl/modules/cplay.py::channelplay_cmd` |
| `/clear` | group | `videl/app/music.py::control` |
| `/clearqueue` | group | `videl/app/music.py::control` |
| `/cplay` | group | `videl/modules/cplay.py::cplay_handler` |
| `/cvplay` | group | `videl/modules/cplay.py::cplay_handler` |
| `/deleteplaylist` | chat | `videl/modules/playlist.py::delete_playlist_cmd` |
| `/download` | group_private | `videl/modules/downloader.py::download_cmd` |
| `/effectoff` | group | `videl/modules/effects.py::effectoff_cmd` |
| `/effecton` | group | `videl/modules/effects.py::effecton_cmd` |
| `/effects` | group | `videl/modules/effects.py::effects_status_cmd` |
| `/end` | group | `videl/app/music.py::control` |
| `/jump` | group | `videl/app/music.py::manage_queue` |
| `/loop` | group | `videl/app/music.py::control` |
| `/lyrics` | chat | `videl/modules/lyrics.py::lyrics_cmd` |
| `/move` | group | `videl/app/music.py::manage_queue` |
| `/pause` | group | `videl/app/music.py::control` |
| `/play` | group | `videl/modules/play.py::play_handler` |
| `/playlist` | group | `videl/modules/playlist.py::load_playlist_cmd` |
| `/playlists` | chat | `videl/modules/playlist.py::list_playlists_cmd` |
| `/playnext` | group | `videl/modules/play.py::play_handler` |
| `/q` | group | `videl/app/music.py::view_queue` |
| `/queue` | group | `videl/app/music.py::view_queue` |
| `/remove` | group | `videl/app/music.py::manage_queue` |
| `/replay` | group | `videl/app/music.py::control` |
| `/resetplayer` | group | `videl/app/music.py::control` |
| `/resume` | group | `videl/app/music.py::control` |
| `/saveplaylist` | group | `videl/modules/playlist.py::save_playlist_cmd` |
| `/seek` | group | `videl/modules/seek.py::seek_cmd` |
| `/seekback` | group | `videl/modules/seek.py::seekback_cmd` |
| `/shuffle` | group | `videl/app/music.py::control` |
| `/skip` | group | `videl/app/music.py::control` |
| `/song` | group_private | `videl/modules/downloader.py::song_cmd` |
| `/speed` | group | `videl/modules/effects.py::speed_cmd` |
| `/speedreset` | group | `videl/modules/effects.py::speedreset_cmd` |
| `/stop` | group | `videl/app/music.py::control` |
| `/voteskip` | group | `videl/modules/smartqueue.py::set_voteskip_cmd` |
| `/vplay` | group | `videl/modules/play.py::play_handler` |
| `/vsong` | group_private | `videl/modules/downloader.py::vsong_cmd` |

## Groups & protection

| Command | Context | Handler |
|---|---|---|
| `/addblacklist` | group | `videl/modules/blocklist.py::addbl_cmd` |
| `/addblsticker` | group | `videl/modules/blocklist.py::add_bl_sticker` |
| `/adminlist` | group | `videl/plugins/moderation.py::admins` |
| `/admins` | group | `videl/plugins/moderation.py::admins` |
| `/adminsummary` | group | `videl/modules/group_manager.py::admin_summary_command` |
| `/antispam` | group | `videl/plugins/locks.py::antispam` |
| `/appeal` | chat | `videl/plugins/appeals.py::appeal` |
| `/appealresolve` | group | `videl/plugins/appeals.py::appealresolve` |
| `/appeals` | group | `videl/plugins/appeals.py::appeals` |
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
| `/commandpreset` | group | `videl/modules/group_manager.py::command_preset_command` |
| `/connect` | chat | `videl/plugins/connections.py::connect` |
| `/connection` | chat | `videl/plugins/connections.py::connection_status` |
| `/dban` | group | `videl/plugins/moderation.py::moderate` |
| `/delblacklist` | group | `videl/modules/blocklist.py::delbl_cmd` |
| `/delblsticker` | group | `videl/modules/blocklist.py::del_bl_sticker` |
| `/delfed` | group | `videl/modules/federation.py::delfed_cmd` |
| `/delnote` | group | `videl/plugins/notes.py::delete_note` |
| `/delphoto` | group | `videl/plugins/group.py::delete_photo` |
| `/demote` | group | `videl/plugins/moderation.py::demote` |
| `/disconnect` | chat | `videl/plugins/connections.py::disconnect` |
| `/dkick` | group | `videl/plugins/moderation.py::moderate` |
| `/dwarn` | group | `videl/plugins/moderation.py::warn` |
| `/faddadmin` | group | `videl/modules/federation.py::fpromote_cmd` |
| `/faq` | group | `videl/plugins/faq.py::faq` |
| `/fban` | chat | `videl/modules/federation.py::fban_cmd` |
| `/fdemote` | group | `videl/modules/federation.py::fdemote_cmd` |
| `/fedbanlist` | chat | `videl/modules/federation.py::fedbanlist_cmd` |
| `/fedchats` | chat | `videl/modules/federation.py::fedchats_cmd` |
| `/fedinfo` | chat | `videl/modules/federation.py::fedinfo_cmd` |
| `/fedstat` | chat | `videl/modules/federation.py::fedinfo_cmd` |
| `/filter` | group | `videl/plugins/notes.py::add_filter` |
| `/filters` | group | `videl/plugins/notes.py::list_filters` |
| `/forgetmember` | group | `videl/plugins/privacy.py::forget_member` |
| `/fpromote` | group | `videl/modules/federation.py::fpromote_cmd` |
| `/fremadmin` | group | `videl/modules/federation.py::fdemote_cmd` |
| `/get` | group | `videl/plugins/notes.py::get` |
| `/goodbye` | group | `videl/plugins/welcome.py::toggle_goodbye` |
| `/greetings` | group | `videl/plugins/welcome.py::greeting_status` |
| `/group` | group | `videl/modules/group_manager.py::group_command` |
| `/groupview` | group | `videl/app/group_view.py::recording` |
| `/handoff` | group | `videl/plugins/moderation.py::handoff` |
| `/invite` | group | `videl/plugins/group.py::invite` |
| `/joinfed` | group | `videl/modules/federation.py::joinfed_cmd` |
| `/kick` | group | `videl/plugins/moderation.py::moderate` |
| `/leavefed` | group | `videl/modules/federation.py::leavefed_cmd` |
| `/lock` | group | `videl/plugins/locks.py::lock` |
| `/locks` | group | `videl/plugins/locks.py::locks` |
| `/maintenance` | group | `videl/modules/group_manager.py::maintenance_command` |
| `/modqueue` | group | `videl/modules/group_manager.py::read_only_modqueue` |
| `/mute` | group | `videl/plugins/moderation.py::moderate` |
| `/myfeds` | chat | `videl/modules/federation.py::myfeds_cmd` |
| `/newfed` | group | `videl/modules/federation.py::newfed_cmd` |
| `/notes` | group | `videl/plugins/notes.py::list_notes` |
| `/permissions` | group | `videl/modules/group_manager.py::permission_command` |
| `/pin` | group | `videl/plugins/group.py::pin` |
| `/promote` | group | `videl/plugins/moderation.py::promote` |
| `/purge` | group | `videl/plugins/group.py::purge` |
| `/raidmode` | group | `videl/plugins/welcome.py::raidmode` |
| `/reason` | group | `videl/plugins/moderation.py::reason_templates` |
| `/report` | group | `videl/plugins/reports.py::report` |
| `/reports` | group | `videl/plugins/reports.py::reports` |
| `/resolve` | group | `videl/plugins/reports.py::resolve` |
| `/retention` | group | `videl/plugins/retention.py::retention` |
| `/reviewer` | group | `videl/modules/group_manager.py::reviewer_command` |
| `/rmblacklist` | group | `videl/modules/blocklist.py::delbl_cmd` |
| `/rulefeedback` | group | `videl/plugins/moderation.py::rule_feedback` |
| `/rules` | group | `videl/plugins/welcome.py::rules` |
| `/safetystats` | group | `videl/plugins/moderation.py::safety_stats` |
| `/save` | group | `videl/plugins/notes.py::save` |
| `/setcaptcha` | group | `videl/plugins/welcome.py::toggle_captcha` |
| `/setchecklist` | group | `videl/plugins/welcome.py::set_checklist` |
| `/setdescription` | group | `videl/plugins/group.py::set_description` |
| `/setfaq` | group | `videl/plugins/faq.py::set_faq` |
| `/setgoodbye` | group | `videl/plugins/welcome.py::set_goodbye` |
| `/setphoto` | group | `videl/plugins/group.py::set_photo` |
| `/setreason` | group | `videl/plugins/moderation.py::set_reason_template` |
| `/setrules` | group | `videl/plugins/welcome.py::set_rules` |
| `/settings` | group | `videl/plugins/settings.py::settings` |
| `/settitle` | group | `videl/plugins/group.py::set_title` |
| `/setup` | group | `videl/plugins/settings.py::settings` |
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
| `/feedback` | chat | `videl/plugins/privacy.py::feedback` |
| `/forget` | chat | `videl/plugins/reminder.py::forget` |
| `/help` | chat | `videl/plugins/help.py::help_command` |
| `/id` | chat | `videl/plugins/tools.py::identifiers` |
| `/inbox` | chat | `videl/app/group_view.py::private_recording` |
| `/kang` | chat | `videl/plugins/stickers.py::kang` |
| `/mydata` | chat | `videl/plugins/privacy.py::my_data` |
| `/ping` | chat | `videl/plugins/tools.py::ping` |
| `/poll` | chat | `videl/plugins/group.py::poll` |
| `/pollstop` | chat | `videl/modules/api_tools.py::stop_poll_command` |
| `/preferences` | chat | `videl/plugins/preferences.py::preferences` |
| `/quiz` | chat | `videl/plugins/group.py::poll` |
| `/react` | chat | `videl/modules/api_tools.py::react_command` |
| `/remind` | chat | `videl/plugins/reminder.py::remind` |
| `/reminders` | chat | `videl/plugins/reminder.py::reminders` |
| `/repo` | chat | `videl/plugins/tools.py::source` |
| `/start` | chat | `videl/plugins/start.py::start` |
| `/stats` | chat | `videl/plugins/group.py::stats` |
| `/stickerid` | chat | `videl/plugins/group.py::sticker_id` |
| `/sudohelp` | chat | `videl/plugins/sudo.py::sudo_help` |
| `/whois` | chat | `videl/plugins/tools.py::whois` |

## Owner operations

| Command | Context | Handler |
|---|---|---|
| `/active` | private | `videl/modules/owner_utils.py::active` |
| `/addsudo` | private | `videl/plugins/sudo.py::add_sudo` |
| `/apiinfo` | private | `videl/modules/api_tools.py::api_info` |
| `/blocklist` | chat | `videl/modules/block.py::blocklist_cmd` |
| `/broadcast` | chat | `videl/modules/broadcast.py::broadcast_cmd` |
| `/dbcleanup` | private | `videl/modules/misc.py::cleanup_cmd` |
| `/delsudo` | private | `videl/plugins/sudo.py::remove_sudo` |
| `/emojiinfo` | private | `videl/modules/api_tools.py::emoji_info` |
| `/feedbacklist` | private | `videl/plugins/privacy.py::feedback_list` |
| `/gblock` | chat | `videl/modules/block.py::gblock_cmd` |
| `/gcast` | chat | `videl/modules/broadcast.py::broadcast_cmd` |
| `/gunblock` | chat | `videl/modules/block.py::gunblock_cmd` |
| `/restart` | private | `videl/modules/voice_admin.py::restart_command` |
| `/rmsudo` | private | `videl/plugins/sudo.py::remove_sudo` |
| `/setbotdescription` | private | `videl/modules/api_tools.py::set_bot_description` |
| `/setbotname` | private | `videl/modules/api_tools.py::set_bot_name` |
| `/setbotphoto` | private | `videl/modules/api_tools.py::set_bot_profile_photo` |
| `/setbotshortdescription` | private | `videl/modules/api_tools.py::set_bot_short_description` |
| `/sudolist` | private | `videl/plugins/sudo.py::sudo_list` |
| `/sysinfo` | private | `videl/modules/owner_utils.py::system_info` |
| `/ublock` | chat | `videl/modules/block.py::ublock_cmd` |
| `/uunblock` | chat | `videl/modules/block.py::uunblock_cmd` |
| `/voicehealth` | private | `videl/modules/voice_admin.py::voice_health_command` |
| `/voicequality` | private | `videl/modules/voice_admin.py::voice_quality_command` |
| `/watchdog` | private | `videl/modules/misc.py::watchdog_cmd` |

## Private-chat connected group commands

Run `/connect` in a group as a current Telegram administrator. From private chat, only these registered commands are routed to that saved group:

`/adminlist`, `/admins`, `/appealresolve`, `/appeals`, `/ban`, `/banlist`, `/clear`, `/clearrules`, `/clearwarns`, `/dban`, `/delnote`, `/demote`, `/dkick`, `/end`, `/filter`, `/filters`, `/get`, `/goodbye`, `/greetings`, `/kick`, `/lock`, `/locks`, `/loop`, `/mute`, `/notes`, `/pause`, `/promote`, `/q`, `/queue`, `/replay`, `/reports`, `/resetplayer`, `/resolve`, `/resume`, `/rules`, `/save`, `/setcaptcha`, `/setdescription`, `/setgoodbye`, `/setrules`, `/settitle`, `/setwarnlimit`, `/setwelcome`, `/shuffle`, `/skip`, `/slowmode`, `/stop`, `/stopfilter`, `/tban`, `/tmute`, `/unban`, `/unlock`, `/unmute`, `/unwarn`, `/warn`, `/warnings`, `/welcome`

Every routed request uses the server-stored group ID, preserves the actual Telegram user, rechecks current group-admin status, and removes private reply targets. Use a username or numeric Telegram ID instead of replying to a private message.

## UI and transport exceptions

Authored command feedback uses the vendored Badmunda05 Richgram helpers and native Kurigram keyboards.
Telegram polls, media/file delivery, forwards/copies, user-authored saved notes, filters and welcome templates
retain their native Telegram transport. They are not wrapped into decorative rich cards or rewritten.
Callback answers remain native short notifications. This is intentional, not an unimplemented rich UI path.
No automatic resend is allowed when a send times out or its outcome is unknown.

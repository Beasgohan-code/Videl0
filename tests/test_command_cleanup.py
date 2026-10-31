"""Keep retired handlers/dependencies out without deleting application data."""
import ast
import unittest
from pathlib import Path
from videl.utils.command_catalog import commands

REMOVED={
    'buttons','features','logs','log','sys','lyric','ly','cplayset','setchannel',
    'setvoteskip','skipvotes','savepl','loadplaylist','loadpl','myplaylists','listpl',
    'delpl','rmplaylist','ytaudio','mdown','yta','ytvideo','vdownload','dl',
    'addapprove','rmapprove','disapprove','approvelist','addbl','rembl','blacklists',
    'blist','blmode','blaction','addblackliststicker','remblsticker','blackliststickers',
    'topicnew','topicrename','topicclose','topicopen','remaind',
}

class CommandCleanupTests(unittest.TestCase):
    def test_removed_names_have_no_registered_handlers(self):
        names={entry['name'] for entry in commands()}
        self.assertFalse(names & REMOVED)
        self.assertTrue({'setup','modernhelp'}.isdisjoint(names))
        for required in ('play','vplay','cplay','autoplay','queue','q','playlist','saveplaylist',
                         'playlists','deleteplaylist','song','vsong','download','ban','warn',
                         'lock','unapprove','addblacklist','rmblacklist','adminlist','permissions',
                         'poll','quiz','copy','remind','watchdog','dbcleanup','tagall'):
            self.assertIn(required,names)

    def test_unused_dependency_declarations_are_gone(self):
        text=Path('requirements.txt').read_text()
        for dependency in ('beautifulsoup4==','lxml==','qrcode[','python-barcode==','pyshorteners==','gtts=='):
            self.assertNotIn(dependency,text)
        for dependency in ('kurigram==','py-tgcalls==','pymongo==','Pillow=='):
            self.assertIn(dependency,text)

    def test_download_routes_are_not_mutually_exclusive(self):
        source=Path('videl/modules/downloader.py').read_text()
        self.assertNotIn('filters.group & filters.private',source)
        self.assertEqual(source.count('(filters.group | filters.private)'),3)

    def test_unused_feature_switches_and_stale_help_are_removed(self):
        tree=ast.parse(Path('config.py').read_text())
        names={node.target.id for node in tree.body if isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name)}
        self.assertFalse(names & {'COMMANDS_HELP','ENABLE_PAID_BROADCAST','ENABLE_BUSINESS','ENABLE_CHECKLIST','ENABLE_DIRECT_MESSAGES','CYBER_DARK','PING_IMG_URL'})

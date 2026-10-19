"""
Videl0 • Watchdog — monitors bot health, restarts, backup to Dropbox
"""
import asyncio, logging, psutil, time, os, json
log=logging.getLogger("videl.watchdog")

async def watchdog_loop(bot):
    from bot.config import LOG_CHANNEL_ID
    log.info("Watchdog started")
    last_ok=time.time()
    while True:
        await asyncio.sleep(300)
        try:
            me=await bot.get_me()
            last_ok=time.time()
            cpu=psutil.cpu_percent(interval=1)
            mem=psutil.virtual_memory().percent
            log.debug(f"Watchdog ok @{me.username} cpu={cpu}% mem={mem}%")
            if time.time()-last_ok > 600 and LOG_CHANNEL_ID:
                try: await bot.send_message(LOG_CHANNEL_ID, f"◍ Watchdog: bot silent for 10m, health check running...")
                except: pass
        except Exception as e:
            log.error(f"Watchdog health check fail: {e}")
            if time.time()-last_ok > 900:
                log.critical("Watchdog: restarting bot process")
                os._exit(1)

async def dropbox_backup_loop():
    from bot.config import DROPBOX_ACCESS_TOKEN, DROPBOX_BACKUP_FOLDER
    if not DROPBOX_ACCESS_TOKEN: return
    log.info("Dropbox backup enabled")
    while True:
        await asyncio.sleep(3600*6)  # every 6h
        try:
            import dropbox
            dbx=dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)
            # backup videl.db
            path="videl.db"
            if os.path.exists(path):
                with open(path,"rb") as f:
                    data=f.read()
                    dbx.files_upload(data, f"{DROPBOX_BACKUP_FOLDER}/videl_{int(time.time())}.db", mode=dropbox.files.WriteMode.overwrite)
                log.info("Dropbox backup done")
        except Exception as e:
            log.warning(f"Dropbox backup fail: {e}")

def start_background(bot):
    asyncio.create_task(watchdog_loop(bot))
    asyncio.create_task(dropbox_backup_loop())

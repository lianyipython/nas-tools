from apscheduler.schedulers.background import BackgroundScheduler
import log
from config import AUTO_REMOVE_TORRENTS_INTERVAL, PT_TRANSFER_INTERVAL, Config, METAINFO_SAVE_INTERVAL, \
    RELOAD_CONFIG_INTERVAL, SYNC_TRANSFER_INTERVAL, RSS_CHECK_INTERVAL, REFRESH_PT_DATA_INTERVAL, \
    RSS_REFRESH_TMDB_INTERVAL, META_DELETE_UNKNOWN_INTERVAL
from pt.douban import DouBan
from pt.downloader import Downloader
from pt.rss import Rss
from pt.sites import Sites
from service.sync import Sync
from utils.functions import singleton
from utils.meta_helper import MetaHelper
from datetime import datetime
import random
import math


@singleton
class Scheduler:
    SCHEDULER = None
    __pt = None
    __douban = None

    def __init__(self):
        self.init_config()

    def init_config(self):
        config = Config()
        self.__pt = config.get_config('pt')
        self.__douban = config.get_config('douban')

    def run_service(self):
        """
        读取配置，启动定时服务
        """
        self.SCHEDULER = BackgroundScheduler(timezone="Asia/Shanghai")
        if not self.SCHEDULER:
            return
        if self.__pt:
            # PT种子清理
            pt_seeding_time = self.__pt.get('pt_seeding_time')
            if pt_seeding_time:
                self.SCHEDULER.add_job(Downloader().pt_removetorrents,
                                       'interval',
                                       seconds=AUTO_REMOVE_TORRENTS_INTERVAL)
                log.info("【RUN】PT下载自动删种服务启动...")

            # PT站签到
            ptsignin_cron = str(self.__pt.get('ptsignin_cron'))
            if ptsignin_cron:
                if '-' in ptsignin_cron:
                    try:
                        time_range = ptsignin_cron.split("-")
                        start_time_range_str = time_range[0]
                        end_time_range_str = time_range[1]
                        start_time_range_array = start_time_range_str.split(":")
                        end_time_range_array = end_time_range_str.split(":")
                        start_hour = int(start_time_range_array[0]) or 1
                        start_minute = int(start_time_range_array[1]) or 1
                        end_hour = int(end_time_range_array[0]) or 1
                        end_minute = int(end_time_range_array[1]) or 1

                        def start_random_job():
                            task_time_count = random.randint(start_hour * 60 + start_minute, end_hour * 60 + end_minute)
                            self.start_data_site_signin_job(math.floor(task_time_count / 60), task_time_count % 60)

                        self.SCHEDULER.add_job(start_random_job,
                                               "cron",
                                               hour=start_hour,
                                               minute=start_minute)
                        log.info("【RUN】PT站自动签到服务时间范围随机模式启动，起始时间于%s:%s" % (
                            str(start_hour).rjust(2, '0'), str(start_minute).rjust(2, '0')))
                    except Exception as e:
                        log.info("【RUN】PT站自动签到时间 时间范围随机模式 配置格式错误：%s %s" % (ptsignin_cron, str(e)))
                elif ptsignin_cron.find(':') != -1:
                    try:
                        hour = int(ptsignin_cron.split(":")[0]) or 1
                        minute = int(ptsignin_cron.split(":")[1]) or 1
                    except Exception as e:
                        log.info("【RUN】PT站自动签到时间 配置格式错误：%s" % str(e))
                        hour = minute = 0
                    if hour and minute:
                        self.SCHEDULER.add_job(Sites().signin,
                                               "cron",
                                               hour=hour,
                                               minute=minute)
                        log.info("【RUN】PT站自动签到服务启动...")
                else:
                    try:
                        hours = float(ptsignin_cron)
                    except Exception as e:
                        log.info("【RUN】PT站自动签到时间 配置格式错误：%s" % str(e))
                        hours = 0
                    if hours:
                        self.SCHEDULER.add_job(Sites().signin,
                                               "interval",
                                               hours=hours)
                        log.info("【RUN】PT站自动签到服务启动...")

            # PT文件转移
            pt_monitor = self.__pt.get('pt_monitor')
            if pt_monitor:
                self.SCHEDULER.add_job(Downloader().pt_transfer, 'interval', seconds=PT_TRANSFER_INTERVAL)
                log.info("【RUN】PT下载文件转移服务启动...")

            # RSS下载器
            pt_check_interval = self.__pt.get('pt_check_interval')
            if pt_check_interval:
                if isinstance(pt_check_interval, str) and pt_check_interval.isdigit():
                    pt_check_interval = int(pt_check_interval)
                else:
                    try:
                        pt_check_interval = round(float(pt_check_interval))
                    except Exception as e:
                        log.error("【RUN】RSS订阅周期 配置格式错误：%s" % str(e))
                        pt_check_interval = 0
                if pt_check_interval:
                    self.SCHEDULER.add_job(Rss().rssdownload, 'interval', seconds=round(pt_check_interval))
                    log.info("【RUN】RSS订阅服务启动...")

            # RSS订阅定时检索
            search_rss_interval = self.__pt.get('search_rss_interval')
            if search_rss_interval:
                if isinstance(search_rss_interval, str) and search_rss_interval.isdigit():
                    search_rss_interval = int(search_rss_interval)
                else:
                    try:
                        search_rss_interval = round(float(search_rss_interval))
                    except Exception as e:
                        log.error("【RUN】订阅定时搜索周期 配置格式错误：%s" % str(e))
                        search_rss_interval = 0
                if search_rss_interval:
                    self.SCHEDULER.add_job(Rss().rsssearch_all, 'interval', hours=search_rss_interval * 24)
                    log.info("【RUN】订阅定时搜索服务启动...")

        # 豆瓣电影同步
        if self.__douban:
            douban_interval = self.__douban.get('interval')
            if douban_interval:
                if isinstance(douban_interval, str):
                    if douban_interval.isdigit():
                        douban_interval = int(douban_interval)
                    else:
                        try:
                            douban_interval = float(douban_interval)
                        except Exception as e:
                            log.info("【RUN】豆瓣同步服务启动失败：%s" % str(e))
                            douban_interval = 0
                if douban_interval:
                    self.SCHEDULER.add_job(DouBan().sync, 'interval', hours=douban_interval)
                    log.info("【RUN】豆瓣同步服务启动...")

        # 配置定时生效
        self.SCHEDULER.add_job(Config().init_config, 'interval', seconds=RELOAD_CONFIG_INTERVAL)

        # 元数据定时保存
        self.SCHEDULER.add_job(MetaHelper().save_meta_data, 'interval', seconds=METAINFO_SAVE_INTERVAL)

        # 定时把队列中的监控文件转移走
        self.SCHEDULER.add_job(Sync().transfer_mon_files, 'interval', seconds=SYNC_TRANSFER_INTERVAL)

        # RSS队列中检索
        self.SCHEDULER.add_job(Rss().rsssearch, 'interval', seconds=RSS_CHECK_INTERVAL)

        # PT站数据刷新
        self.SCHEDULER.add_job(Sites().refresh_pt_date_now, 'interval', hours=REFRESH_PT_DATA_INTERVAL)

        # 豆瓣RSS转TMDB，定时更新TMDB数据
        self.SCHEDULER.add_job(Rss().refresh_rss_metainfo, 'interval', hours=RSS_REFRESH_TMDB_INTERVAL)

        # 定时清除未识别的缓存
        self.SCHEDULER.add_job(MetaHelper().delete_unknown_meta, 'interval', hours=META_DELETE_UNKNOWN_INTERVAL)

        self.SCHEDULER.print_jobs()

        self.SCHEDULER.start()

    def stop_service(self):
        """
        停止定时服务
        """
        try:
            if self.SCHEDULER:
                self.SCHEDULER.remove_all_jobs()
                self.SCHEDULER.shutdown()
                self.SCHEDULER = None
        except Exception as e:
            print(str(e))

    def start_data_site_signin_job(self, hour, minute):
        year = datetime.now().year
        month = datetime.now().month
        day = datetime.now().day
        # 随机数从1秒开始，不在整点签到
        second = random.randint(1, 59)
        log.info("【RUN】PT站自动签到时间 即将在%s-%s-%s,%s:%s:%s签到" % (
            str(year), str(month), str(day), str(hour), str(minute), str(second)))
        if hour < 0 or hour > 24:
            hour = -1
        if minute < 0 or minute > 60:
            minute = -1
        if hour < 0 or minute < 0:
            log.warn("【RUN】PT站自动签到时间 配置格式错误：不启动任务")
            return
        self.SCHEDULER.add_job(Sites().signin,
                               "date",
                               run_date=datetime(year, month, day, hour, minute, second))

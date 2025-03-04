import re
from config import RMT_MEDIAEXT
from rmt.meta.metabase import MetaBase
from utils.functions import is_chinese
from utils.tokens import Tokens
from utils.types import MediaType


class MetaVideo(MetaBase):
    """
    识别电影、电视剧
    """
    # 控制标位区
    _stop_name_flag = False
    _last_token = ""
    _last_token_type = ""
    _continue_flag = True
    _unknown_name_str = ""
    # 正则式区
    _season_re = r"S(\d{2})|^S(\d{1,2})|S(\d{1,2})E"
    _episode_re = r"EP?(\d{2,4})|^EP?(\d{1,4})|S\d{1,2}EP?(\d{1,4})"
    _part_re = r"(^PART[0-9ABI]{0,2}$|^CD[0-9]{0,2}$|^DVD[0-9]{0,2}$|^DISK[0-9]{0,2}$|^DISC[0-9]{0,2}$)"
    _roman_numerals = r"^(?=[MDCLXVI])M*(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})$"
    _resources_type_re = r"^BLURAY$|^REMUX$|^HDTV$|^UHDTV$|^HDDVD$|^WEBRIP$|^DVDRIP$|^BDRIP$|^UHD$|^SDR$|^HDR\d*$|^DOLBY$|^BLU$|^WEB$|^BD$"
    _name_no_begin_re = r"^\[.+?]"
    _name_se_words = ['共', '第', '季', '集', '话', '話']
    _name_nostring_re = r"^PTS|^JADE|^AOD|^CHC|^[A-Z]{1,4}TV[\-0-9UVHDK]*|HBO|\d{1,2}th|\d{1,2}bit|NETFLIX|AMAZON|IMAX|^3D|\s+3D|BBC|DISNEY\+?|XXX|\s+DC$" \
                        r"|[第\s共]+[0-9一二三四五六七八九十\-\s]+季" \
                        r"|[第\s共]+[0-9一二三四五六七八九十\-\s]+[集话話]" \
                        r"|连载|日剧|美剧|电视剧|动画片|动漫|欧美|西德|日韩|超高清|高清|蓝光|翡翠台|梦幻天堂·龙网" \
                        r"|最终季|合集|[多中国英葡法俄日韩德意西印泰台港粤双文语简繁体特效内封官译外挂]+字幕|版本|出品|台版|港版" \
                        r"|未删减版|UNCUT$|UNRATE$|WITH EXTRAS$|RERIP$|SUBBED$|PROPER$|REPACK$|SEASON$|EPISODE$" \
                        r"|S\d{2}\s*-\s*S\d{2}|S\d{2}|\s+S\d{1,2}|EP?\d{2,4}\s*-\s*EP?\d{2,4}|EP?\d{2,4}|\s+EP?\d{1,4}" \
                        r"|CD[\s.]*[1-9]|DVD[\s.]*[1-9]|DISK[\s.]*[1-9]|DISC[\s.]*[1-9]" \
                        r"|[248]K|\d{3,4}[PIX]+" \
                        r"|CD[\s.]*[1-9]|DVD[\s.]*[1-9]|DISK[\s.]*[1-9]|DISC[\s.]*[1-9]"
    _resources_pix_re = r"^[SBUHD]*(\d{3,4}[PIX]+)"
    _resources_pix_re2 = r"(^[248]+K)"
    _video_encode_re = r"^[HX]26[45]$|^AVC$|^HEVC$|^VC\d?$|^MPEG\d?$|^Xvid$|^DivX$|^HDR\d*$"
    _audio_encode_re = r"^DTS\d?$|^DTSHD$|^DTSHDMA$|^Atmos$|^TrueHD\d?$|^AC3$|^\dAudios?$|^DDP\d?$|^DD\d?$|^LPCM\d?$|^AAC\d?$|^FLAC\d?$|^HD\d?$|^MA\d?$"

    def __init__(self, title, subtitle=None):
        super().__init__(title, subtitle)
        if not title:
            return
        # 去掉名称中第1个[]的内容
        title = re.sub(r'%s' % self._name_no_begin_re, "", title, count=1)
        # 把xxxx-xxxx年份换成前一个年份，常出现在季集上
        title = re.sub(r'([\s.]+)(\d{4})-(\d{4})', r'\1\2', title)
        # 把大小去掉
        title = re.sub(r'[0-9.]+\s*[MGT]i?B(?![A-Z]+)', "", title, flags=re.IGNORECASE)
        # 把年月日去掉
        title = re.sub(r'\d{4}[\s._-]\d{1,2}[\s._-]\d{1,2}', "", title)
        # 拆分tokens
        tokens = Tokens(title)
        self.tokens = tokens
        # 解析名称、年份、季、集、资源类型、分辨率等
        token = tokens.get_next()
        while token:
            # Part
            self.__init_part(token)
            # 标题
            if self._continue_flag:
                self.__init_name(token)
            # 年份
            if self._continue_flag:
                self.__init_year(token)
            # 分辨率
            if self._continue_flag:
                self.__init_resource_pix(token)
            # 季
            if self._continue_flag:
                self.__init_seasion(token)
            # 集
            if self._continue_flag:
                self.__init_episode(token)
            # 资源类型
            if self._continue_flag:
                self.__init_resource_type(token)
            # 视频编码
            if self._continue_flag:
                self.__init_video_encode(token)
            # 音频编码
            if self._continue_flag:
                self.__init_audio_encode(token)
            # 取下一个，直到没有为卡
            token = tokens.get_next()
            self._continue_flag = True
        # 解析副标题，只要季和集
        self.init_subtitle(title)
        if not self._subtitle_flag and subtitle:
            self.init_subtitle(subtitle)
        # 没有识别出类型时默认为电影
        if not self.type:
            self.type = MediaType.MOVIE
        # 去掉名字中不需要的干扰字符，过短的纯数字不要
        self.cn_name = self.__fix_name(self.cn_name)
        self.en_name = self.__fix_name(self.en_name)
        # 处理part
        if self.part and self.part.upper() == "PART":
            self.part = None

    def __fix_name(self, name):
        if not name:
            return name
        name = re.sub(r'%s' % self._name_nostring_re, '', name,
                      flags=re.IGNORECASE).strip()
        name = re.sub(r'\s+', ' ', name)
        if name.isdigit() and int(name) < 1800:
            if self.begin_episode is None:
                self.begin_episode = int(name)
                name = None
            elif self.is_in_episode(int(name)):
                name = None
        return name

    def __init_name(self, token):
        if not token:
            return
        # 回收标题
        if self._unknown_name_str and not self.get_name():
            self.en_name = self._unknown_name_str
            self._unknown_name_str = ""
        if self._stop_name_flag:
            if self._unknown_name_str and self._unknown_name_str != self.year:
                if self.en_name:
                    self.en_name = "%s %s" % (self.en_name, self._unknown_name_str)
                else:
                    self.cn_name = "%s %s" % (self.cn_name, self._unknown_name_str)
                self._unknown_name_str = ""
            return
        if token in self._name_se_words:
            self._last_token_type = 'name_se_words'
            return
        if is_chinese(token):
            # 含有中文，直接做为标题（连着的数字或者英文会保留），且不再取用后面出现的中文
            if not self.cn_name and token:
                self.cn_name = token
                self._last_token_type = "cnname"
        else:
            is_roman_digit = re.search(self._roman_numerals, token)
            # 阿拉伯数字或者罗马数字
            if token.isdigit() or is_roman_digit:
                # 第季集后面的不要
                if self._last_token_type == 'name_se_words':
                    return
                if self.get_name():
                    # 名字后面以 0 开头的不要，极有可能是集
                    if token.startswith('0'):
                        return
                    if (token.isdigit() and len(token) < 4) or is_roman_digit:
                        # 4位以下的数字或者罗马数字，拼装到已有标题中
                        if self._last_token_type == "cnname":
                            self.cn_name = "%s %s" % (self.cn_name, token)
                        elif self._last_token_type == "enname":
                            self.en_name = "%s %s" % (self.en_name, token)
                        self._continue_flag = False
                    elif token.isdigit() and len(token) == 4:
                        # 4位数字，可能是年份，也可能真的是标题的一部分，也有可能是集
                        if token.startswith('0') or not 1900 < int(token) < 2050:
                            return
                        if not self._unknown_name_str:
                            self._unknown_name_str = token
                else:
                    # 名字未出现前的第一个数字，记下来
                    if not self._unknown_name_str:
                        self._unknown_name_str = token
            elif re.search(r"%s" % self._season_re, token, re.IGNORECASE) \
                    or re.search(r"%s" % self._episode_re, token, re.IGNORECASE) \
                    or re.search(r"(%s)" % self._resources_type_re, token, re.IGNORECASE) \
                    or re.search(r"%s" % self._resources_pix_re, token, re.IGNORECASE):
                # 季集等不要
                self._stop_name_flag = True
                return
            else:
                # 后缀名不要
                if ".%s".lower() % token in RMT_MEDIAEXT:
                    return
                # 英文或者英文+数字，拼装起来
                if self.en_name:
                    self.en_name = "%s %s" % (self.en_name, token)
                else:
                    self.en_name = token
                self._last_token_type = "enname"

    def __init_part(self, token):
        if not self.get_name():
            return
        if not self.year \
                and not self.begin_season \
                and not self.begin_episode \
                and not self.resource_pix \
                and not self.resource_type:
            return
        re_res = re.search(r"%s" % self._part_re, token, re.IGNORECASE)
        if re_res:
            if not self.part:
                self.part = re_res.group(1)
            nextv = self.tokens.cur()
            if nextv \
                    and ((nextv.isdigit() and (len(nextv) == 1 or len(nextv) == 2 and nextv.startswith('0')))
                         or nextv.upper() in ['A', 'B', 'C', 'I', 'II', 'III']):
                self.part = "%s%s" % (self.part, nextv)
                self.tokens.get_next()
            self._last_token_type = "part"
            self._continue_flag = False
            self._stop_name_flag = False

    def __init_year(self, token):
        if not self.get_name():
            return
        if not token.isdigit():
            return
        if len(token) != 4:
            return
        if not 1900 < int(token) < 2050:
            return
        self.year = token
        self._last_token_type = "year"
        self._continue_flag = False
        self._stop_name_flag = True

    def __init_resource_pix(self, token):
        if not self.get_name():
            return
        re_res = re.search(r"%s" % self._resources_pix_re, token, re.IGNORECASE)
        if re_res:
            self._last_token_type = "pix"
            self._continue_flag = False
            self._stop_name_flag = True
            if not self.resource_pix:
                self.resource_pix = re_res.group(1).lower()
            elif self.resource_pix == "3D":
                self.resource_pix = "%s 3D" % re_res.group(1).lower()
        else:
            re_res = re.search(r"%s" % self._resources_pix_re2, token, re.IGNORECASE)
            if re_res:
                self._last_token_type = "pix"
                self._continue_flag = False
                self._stop_name_flag = True
                if not self.resource_pix:
                    self.resource_pix = re_res.group(1).lower()
                elif self.resource_pix == "3D":
                    self.resource_pix = "%s 3D" % re_res.group(1).lower()
            elif token.upper() == "3D":
                self._last_token_type = "pix"
                self._continue_flag = False
                self._stop_name_flag = True
                if not self.resource_pix:
                    self.resource_pix = "3D"
                else:
                    self.resource_pix = "%s 3D" % self.resource_pix

    def __init_seasion(self, token):
        if not self.get_name():
            return
        re_res = re.findall(r"%s" % self._season_re, token, re.IGNORECASE)
        if re_res:
            self._last_token_type = "season"
            self.type = MediaType.TV
            self._stop_name_flag = True
            self._continue_flag = True
            for se in re_res:
                if isinstance(se, tuple):
                    se_t = None
                    for se_i in se:
                        if se_i and str(se_i).isdigit():
                            se_t = se_i
                            break
                    if se_t:
                        se = int(se_t)
                else:
                    se = int(se)
                if self.begin_season is None:
                    self.begin_season = se
                    self.total_seasons = 1
                else:
                    if self.begin_season != se:
                        self.end_season = se
                        self.total_seasons = (self.end_season - self.begin_season) + 1
        elif token.isdigit():
            if self.begin_season is not None \
                    and self.end_season is None \
                    and len(token) < 3 \
                    and int(token) > self.begin_season \
                    and self._last_token_type == "season" \
                    and (not self.tokens.cur() or not self.tokens.cur().isdigit()):
                self.end_season = int(token)
                self.total_seasons = (self.end_season - self.begin_season) + 1
                self._continue_flag = False
            elif self._last_token_type == "SEASON" \
                    and self.begin_season is None \
                    and len(token) < 3:
                self.begin_season = int(token)
                self.total_seasons = 1
                self._last_token_type = "season"
                self._stop_name_flag = True
                self._continue_flag = False
                self.type = MediaType.TV
        elif token.upper() == "SEASON" and self.begin_season is None:
            self._last_token_type = "SEASON"

    def __init_episode(self, token):
        if not self.get_name():
            return
        re_res = re.findall(r"%s" % self._episode_re, token, re.IGNORECASE)
        if re_res:
            self._last_token_type = "episode"
            self._continue_flag = False
            self._stop_name_flag = True
            self.type = MediaType.TV
            for se in re_res:
                if isinstance(se, tuple):
                    se_t = None
                    for se_i in se:
                        if se_i and str(se_i).isdigit():
                            se_t = se_i
                            break
                    if se_t:
                        se = int(se_t)
                else:
                    se = int(se)
                if self.begin_episode is None:
                    self.begin_episode = se
                    self.total_episodes = 1
                else:
                    if self.begin_episode != se:
                        self.end_episode = se
                        self.total_episodes = (self.end_episode - self.begin_episode) + 1
        elif token.isdigit():
            if self.begin_episode is not None \
                    and self.end_episode is None \
                    and len(token) < 5 \
                    and int(token) > self.begin_episode \
                    and self._last_token_type == "episode":
                self.end_episode = int(token)
                self.total_episodes = (self.end_episode - self.begin_episode) + 1
                self._continue_flag = False
            elif self.begin_episode is None \
                    and 1 < len(token) < 5 \
                    and self._last_token_type != "year" \
                    and self._last_token_type != "videoencode":
                self.begin_episode = int(token)
                self.total_episodes = 1
                self._last_token_type = "episode"
                self._continue_flag = False
                self._stop_name_flag = True
                self.type = MediaType.TV
            elif self._last_token_type == "EPISODE" \
                    and self.begin_episode is None \
                    and len(token) < 5:
                self.begin_episode = int(token)
                self.total_episodes = 1
                self._last_token_type = "episode"
                self._continue_flag = False
                self._stop_name_flag = True
                self.type = MediaType.TV
        elif token.upper() == "EPISODE":
            self._last_token_type = "EPISODE"

    def __init_resource_type(self, token):
        if not self.get_name():
            return
        re_res = re.search(r"(%s)" % self._resources_type_re, token, re.IGNORECASE)
        if re_res:
            self._last_token_type = "restype"
            self._continue_flag = False
            self._stop_name_flag = True
            if not self.resource_type:
                self.resource_type = re_res.group(1)
                self._last_token = self.resource_type.upper()

        else:
            if token.upper() == "DL" \
                    and self._last_token_type == "restype" \
                    and self._last_token == "WEB":
                self.resource_type = "WEB-DL"
                self._continue_flag = False
            if token.upper() == "RAY" \
                    and self._last_token_type == "restype" \
                    and self._last_token == "BLU":
                self.resource_type = "BluRay"
                self._continue_flag = False

    def __init_video_encode(self, token):
        if not self.get_name():
            return
        if not self.year \
                and not self.resource_pix \
                and not self.resource_type \
                and not self.begin_season \
                and not self.begin_episode:
            return
        re_res = re.search(r"(%s)" % self._video_encode_re, token, re.IGNORECASE)
        if re_res:
            self._continue_flag = False
            self._stop_name_flag = True
            self._last_token_type = "videoencode"
            if not self.video_encode:
                self.video_encode = re_res.group(1)
                self._last_token = re_res.group(1).upper()
        elif token.upper() in ['H', 'X']:
            self._continue_flag = False
            self._stop_name_flag = True
            self._last_token_type = "videoencode"
            self._last_token = token.upper()
        elif token.isdigit() \
                and self._last_token_type == "videoencode" \
                and self._last_token in ['H', 'X']:
            self.video_encode = "%s%s" % (self._last_token, token)
        elif token.isdigit() \
                and self._last_token_type == "videoencode" \
                and self._last_token in ['VC', 'MPEG']:
            self.video_encode = "%s%s" % (self._last_token, token)

    def __init_audio_encode(self, token):
        if not self.get_name():
            return
        if not self.year \
                and not self.resource_pix \
                and not self.resource_type \
                and not self.begin_season \
                and not self.begin_episode:
            return
        re_res = re.search(r"(%s)" % self._audio_encode_re, token, re.IGNORECASE)
        if re_res:
            self._continue_flag = False
            self._stop_name_flag = True
            self._last_token_type = "audioencode"
            self._last_token = re_res.group(1).upper()
            if not self.audio_encode:
                self.audio_encode = re_res.group(1)
            else:
                if self.audio_encode.upper() == "DTS":
                    self.audio_encode = "%s-%s" % (self.audio_encode, re_res.group(1))
                else:
                    self.audio_encode = "%s %s" % (self.audio_encode, re_res.group(1))
        elif token.isdigit() \
                and self._last_token_type == "audioencode":
            if self.audio_encode:
                if self._last_token.isdigit():
                    self.audio_encode = "%s.%s" % (self.audio_encode, token)
                elif self.audio_encode[-1].isdigit():
                    self.audio_encode = "%s %s.%s" % (self.audio_encode[:-1], self.audio_encode[-1], token)
                else:
                    self.audio_encode = "%s %s" % (self.audio_encode, token)
            self._last_token = token

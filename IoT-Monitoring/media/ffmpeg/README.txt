FFmpeg 64-bit static Windows build from www.gyan.dev

Version: 2026-07-23-git-80eb9e99b9-full_build-www.gyan.dev

License: GPL v3

Source Code: https://github.com/FFmpeg/FFmpeg/commit/80eb9e99b9

External Assets
frei0r plugins:   https://www.gyan.dev/ffmpeg/builds/ffmpeg-frei0r-plugins
lensfun database: https://www.gyan.dev/ffmpeg/builds/ffmpeg-lensfun-db
whisper models:   https://huggingface.co/ggerganov/whisper.cpp/tree/main

git-full build configuration: 

ARCH                      x86 (generic)
big-endian                no
runtime cpu detection     yes
standalone assembly       yes
x86 assembler             nasm
MMX enabled               yes
MMXEXT enabled            yes
SSE enabled               yes
SSSE3 enabled             yes
AESNI enabled             yes
CLMUL enabled             yes
AVX enabled               yes
AVX2 enabled              yes
AVX-512 enabled           yes
AVX-512ICL enabled        yes
XOP enabled               yes
FMA3 enabled              yes
FMA4 enabled              yes
i686 features enabled     yes
CMOV is fast              yes
EBX available             yes
6 registers available     yes
7 registers available     yes
debug symbols             yes
strip symbols             yes
optimize for size         no
optimizations             yes
static                    yes
shared                    no
network support           yes
threading support         pthreads
safe bitstream reader     yes
texi2html enabled         no
perl enabled              yes
pod2man enabled           yes
makeinfo enabled          yes
makeinfo supports HTML    yes
experimental features     yes
xmllint enabled           yes

External libraries:
avisynth                libgsm                  libsvtjpegxs
bzlib                   libharfbuzz             libtheora
cairo                   libilbc                 libtwolame
chromaprint             libjxl                  libuavs3d
frei0r                  liblc3                  libvidstab
gmp                     liblensfun              libvmaf
gnutls                  libmodplug              libvo_amrwbenc
iconv                   libmp3lame              libvorbis
ladspa                  libmysofa               libvpx
lcms2                   liboapv                 libvvenc
libaom                  libopencore_amrnb       libwebp
libaribb24              libopencore_amrwb       libx264
libaribcaption          libopenjpeg             libx265
libass                  libopenmpt              libxavs2
libbluray               libopus                 libxevd
libbs2b                 libplacebo              libxeve
libcaca                 libqrencode             libxml2
libcdio                 libquirc                libxvid
libcodec2               librav1e                libzimg
libdav1d                librist                 libzmq
libdavs2                librubberband           libzvbi
libdvdnav               libshine                lzma
libdvdread              libsnappy               mediafoundation
libflite                libsoxr                 openal
libfontconfig           libspeex                sdl2
libfreetype             libsrt                  whisper
libfribidi              libssh                  zlib
libgme                  libsvtav1

External libraries providing hardware acceleration:
amf                     d3d12va                 nvdec
cuda                    dxva2                   nvenc
cuda_llvm               ffnvcodec               opencl
cuvid                   libmfx                  vaapi
d3d11va                 libvpl                  vulkan

Libraries:
avcodec                 avformat                swscale
avdevice                avutil
avfilter                swresample

Programs:
ffmpeg                  ffplay                  ffprobe

Enabled decoders:
aac                     flv                     pcm_u24be
aac_fixed               fmvc                    pcm_u24le
aac_latm                fourxm                  pcm_u32be
aasc                    fraps                   pcm_u32le
ac3                     frwu                    pcm_u8
ac3_fixed               ftr                     pcm_vidc
acelp_kelvin            g2m                     pcx
adpcm_4xm               g723_1                  pdv
adpcm_adx               g728                    pfm
adpcm_afc               g729                    pgm
adpcm_agm               gdv                     pgmyuv
adpcm_aica              gem                     pgssub
adpcm_argo              gif                     pgx
adpcm_circus            gremlin_dpcm            phm
adpcm_ct                gsm                     photocd
adpcm_dtk               gsm_ms                  pictor
adpcm_ea                h261                    pixlet
adpcm_ea_maxis_xa       h263                    pjs
adpcm_ea_r1             h263i                   png
adpcm_ea_r2             h263p                   ppm
adpcm_ea_r3             h264                    prores
adpcm_ea_xas            h264_amf                prores_raw
adpcm_g722              h264_cuvid              prosumer
adpcm_g726              h264_qsv                psd
adpcm_g726le            hap                     ptx
adpcm_ima_acorn         hca                     qcelp
adpcm_ima_alp           hcom                    qdm2
adpcm_ima_amv           hdr                     qdmc
adpcm_ima_apc           hevc                    qdraw
adpcm_ima_apm           hevc_amf                qoa
adpcm_ima_cunning       hevc_cuvid              qoi
adpcm_ima_dat4          hevc_qsv                qpeg
adpcm_ima_dk3           hnm4_video              qtrle
adpcm_ima_dk4           hq_hqa                  r10k
adpcm_ima_ea_eacs       hqx                     r210
adpcm_ima_ea_sead       huffyuv                 ra_144
adpcm_ima_escape        hymt                    ra_288
adpcm_ima_hvqm2         iac                     ralf
adpcm_ima_hvqm4         idcin                   rasc
adpcm_ima_iss           idf                     rawvideo
adpcm_ima_magix         iff_ilbm                realtext
adpcm_ima_moflex        ilbc                    rka
adpcm_ima_mtf           imc                     rl2
adpcm_ima_oki           imm4                    roq
adpcm_ima_pda           imm5                    roq_dpcm
adpcm_ima_qt            indeo2                  rpza
adpcm_ima_rad           indeo3                  rscc
adpcm_ima_smjpeg        indeo4                  rtv1
adpcm_ima_ssi           indeo5                  rv10
adpcm_ima_wav           interplay_acm           rv20
adpcm_ima_ws            interplay_dpcm          rv30
adpcm_ima_xbox          interplay_video         rv40
adpcm_ms                ipu                     rv60
adpcm_mtaf              jacosub                 s302m
adpcm_n64               jpeg2000                sami
adpcm_psx               jpegls                  sanm
adpcm_psxc              jv                      sbc
adpcm_sanyo             kgv1                    scpr
adpcm_sbpro_2           kmvc                    screenpresso
adpcm_sbpro_3           lagarith                sdx2_dpcm
adpcm_sbpro_4           lead                    sga
adpcm_swf               libaom_av1              sgi
adpcm_thp               libaribb24              sgirle
adpcm_thp_le            libaribcaption          sheervideo
adpcm_vima              libcodec2               shorten
adpcm_xa                libdav1d                simbiosis_imx
adpcm_xmd               libdavs2                sipr
adpcm_yamaha            libgsm                  siren
adpcm_zork              libgsm_ms               smackaud
agm                     libilbc                 smacker
ahx                     libjxl                  smc
aic                     libjxl_anim             smvjpeg
alac                    liblc3                  snow
alias_pix               libopencore_amrnb       sol_dpcm
als                     libopencore_amrwb       sp5x
amrnb                   libopus                 speedhq
amrwb                   libspeex                speex
amv                     libsvtjpegxs            srgc
anm                     libuavs3d               srt
ansi                    libvorbis               ssa
anull                   libvpx_vp8              stl
apac                    libvpx_vp9              subrip
ape                     libxevd                 subviewer
apng                    libzvbi_teletext        subviewer1
aptx                    loco                    sunrast
aptx_hd                 lscr                    svq1
apv                     m101                    svq3
arbc                    mace3                   tak
argo                    mace6                   targa
ass                     magicyuv                targa_y216
asv1                    mdec                    tdsc
asv2                    media100                text
atrac1                  metasound               theora
atrac3                  microdvd                thp
atrac3al                mimic                   tiertexseqvideo
atrac3p                 misc4                   tiff
atrac3pal               mjpeg                   tmv
atrac9                  mjpeg_cuvid             truehd
aura                    mjpeg_qsv               truemotion1
aura2                   mjpegb                  truemotion2
av1                     mlp                     truemotion2rt
av1_amf                 mmvideo                 truespeech
av1_cuvid               mobiclip                tscc
av1_qsv                 motionpixels            tscc2
avrn                    movtext                 tta
avrp                    mp1                     twinvq
avs                     mp1float                txd
avui                    mp2                     ulti
bethsoftvid             mp2float                utvideo
bfi                     mp3                     v210
bink                    mp3adu                  v210x
binkaudio_dct           mp3adufloat             vb
binkaudio_rdft          mp3float                vble
bintext                 mp3on4                  vbn
bitpacked               mp3on4float             vc1
bmp                     mpc7                    vc1_cuvid
bmv_audio               mpc8                    vc1_qsv
bmv_video               mpeg1_cuvid             vc1image
bonk                    mpeg1video              vcr1
brender_pix             mpeg2_cuvid             vmdaudio
c93                     mpeg2_qsv               vmdvideo
cavs                    mpeg2video              vmix
cbd2_dpcm               mpeg4                   vmnc
ccaption                mpeg4_cuvid             vnull
cdgraphics              mpegvideo               vorbis
cdtoons                 mpl2                    vp3
cdxl                    msa1                    vp4
cfhd                    mscc                    vp5
cinepak                 msmpeg4v1               vp6
clearvideo              msmpeg4v2               vp6a
cljr                    msmpeg4v3               vp6f
cllc                    msnsiren                vp7
comfortnoise            msp2                    vp8
cook                    msrle                   vp8_cuvid
cpia                    mss1                    vp8_qsv
cri                     mss2                    vp9
cscd                    msvideo1                vp9_amf
cyuv                    mszh                    vp9_cuvid
dca                     mts2                    vp9_qsv
dds                     mv30                    vplayer
derf_dpcm               mvc1                    vqa
dfa                     mvc2                    vqc
dfpwm                   mvdv                    vvc
dirac                   mvha                    vvc_qsv
dnxhd                   mwsc                    wady_dpcm
dolby_e                 mxpeg                   wavarc
dpx                     nellymoser              wavpack
dsd_lsbf                notchlc                 wbmp
dsd_lsbf_planar         nuv                     wcmv
dsd_msbf                on2avc                  webp
dsd_msbf_planar         opus                    webp_anim
dsicinaudio             osq                     webvtt
dsicinvideo             paf_audio               wmalossless
dss_sp                  paf_video               wmapro
dst                     pam                     wmav1
dvaudio                 pbm                     wmav2
dvbsub                  pcm_alaw                wmavoice
dvdsub                  pcm_bluray              wmv1
dvvideo                 pcm_dvd                 wmv2
dxa                     pcm_f16le               wmv3
dxtory                  pcm_f24le               wmv3image
dxv                     pcm_f32be               wnv1
eac3                    pcm_f32le               wrapped_avframe
eacmv                   pcm_f64be               ws_snd1
eamad                   pcm_f64le               xan_dpcm
eatgq                   pcm_lxf                 xan_wc3
eatgv                   pcm_mulaw               xan_wc4
eatqi                   pcm_s16be               xbin
eightbps                pcm_s16be_planar        xbm
eightsvx_exp            pcm_s16le               xface
eightsvx_fib            pcm_s16le_planar        xl
escape124               pcm_s24be               xma1
escape130               pcm_s24daud             xma2
evrc                    pcm_s24le               xpm
exr                     pcm_s24le_planar        xsub
fastaudio               pcm_s32be               xwd
ffv1                    pcm_s32le               y41p
ffvhuff                 pcm_s32le_planar        ylc
ffwavesynth             pcm_s64be               yop
fic                     pcm_s64le               yuv4
fits                    pcm_s8                  zero12v
flac                    pcm_s8_planar           zerocodec
flashsv                 pcm_sga                 zlib
flashsv2                pcm_u16be               zmbv
flic                    pcm_u16le

Enabled encoders:
a64multi                hevc_d3d12va            pcm_s32be
a64multi5               hevc_mf                 pcm_s32le
aac                     hevc_nvenc              pcm_s32le_planar
aac_mf                  hevc_qsv                pcm_s64be
ac3                     hevc_vaapi              pcm_s64le
ac3_fixed               hevc_vulkan             pcm_s8
ac3_mf                  huffyuv                 pcm_s8_planar
adpcm_adx               jpeg2000                pcm_u16be
adpcm_argo              jpegls                  pcm_u16le
adpcm_g722              libaom_av1              pcm_u24be
adpcm_g726              libcodec2               pcm_u24le
adpcm_g726le            libgsm                  pcm_u32be
adpcm_ima_alp           libgsm_ms               pcm_u32le
adpcm_ima_amv           libilbc                 pcm_u8
adpcm_ima_apm           libjxl                  pcm_vidc
adpcm_ima_qt            libjxl_anim             pcx
adpcm_ima_ssi           liblc3                  pdv
adpcm_ima_wav           libmp3lame              pfm
adpcm_ima_ws            liboapv                 pgm
adpcm_ms                libopencore_amrnb       pgmyuv
adpcm_swf               libopenjpeg             phm
adpcm_yamaha            libopus                 png
alac                    librav1e                ppm
alias_pix               libshine                prores
amv                     libspeex                prores_aw
anull                   libsvtav1               prores_ks
apng                    libsvtjpegxs            prores_ks_vulkan
aptx                    libtheora               qoi
aptx_hd                 libtwolame              qtrle
apv_vulkan              libvo_amrwbenc          r10k
ass                     libvorbis               r210
asv1                    libvpx_vp8              ra_144
asv2                    libvpx_vp9              rawvideo
av1_amf                 libvvenc                roq
av1_d3d12va             libwebp                 roq_dpcm
av1_mf                  libwebp_anim            rpza
av1_nvenc               libx264                 rv10
av1_qsv                 libx264rgb              rv20
av1_vaapi               libx265                 s302m
av1_vulkan              libxavs2                sbc
avrp                    libxeve                 sgi
avui                    libxvid                 smc
bitpacked               ljpeg                   snow
bmp                     magicyuv                speedhq
cfhd                    mjpeg                   srt
cinepak                 mjpeg_qsv               ssa
cljr                    mjpeg_vaapi             subrip
comfortnoise            mlp                     sunrast
dca                     movtext                 svq1
dfpwm                   mp2                     targa
dnxhd                   mp2fixed                text
dpx                     mp3_mf                  tiff
dvbsub                  mpeg1video              truehd
dvdsub                  mpeg2_qsv               tta
dvvideo                 mpeg2_vaapi             ttml
dxv                     mpeg2video              utvideo
eac3                    mpeg4                   v210
exr                     msmpeg4v2               vbn
ffv1                    msmpeg4v3               vc2
ffv1_vulkan             msrle                   vnull
ffvhuff                 msvideo1                vorbis
fits                    nellymoser              vp8_vaapi
flac                    opus                    vp9_qsv
flashsv                 pam                     vp9_vaapi
flashsv2                pbm                     wavpack
flv                     pcm_alaw                wbmp
g723_1                  pcm_bluray              webvtt
gif                     pcm_dvd                 wmav1
h261                    pcm_f32be               wmav2
h263                    pcm_f32le               wmv1
h263p                   pcm_f64be               wmv2
h264_amf                pcm_f64le               wrapped_avframe
h264_d3d12va            pcm_mulaw               xbm
h264_mf                 pcm_s16be               xface
h264_nvenc              pcm_s16be_planar        xsub
h264_qsv                pcm_s16le               xwd
h264_vaapi              pcm_s16le_planar        y41p
h264_vulkan             pcm_s24be               yuv4
hap                     pcm_s24daud             zlib
hdr                     pcm_s24le               zmbv
hevc_amf                pcm_s24le_planar

Enabled hwaccels:
apv_vulkan              hevc_nvdec              vc1_nvdec
av1_d3d11va             hevc_nvdec_cuarray      vc1_nvdec_cuarray
av1_d3d11va2            hevc_vaapi              vc1_vaapi
av1_d3d12va             hevc_vulkan             vp8_nvdec
av1_dxva2               mjpeg_nvdec             vp8_nvdec_cuarray
av1_nvdec               mjpeg_vaapi             vp8_vaapi
av1_nvdec_cuarray       mpeg1_nvdec             vp9_d3d11va
av1_vaapi               mpeg1_nvdec_cuarray     vp9_d3d11va2
av1_vulkan              mpeg2_d3d11va           vp9_d3d12va
dpx_vulkan              mpeg2_d3d11va2          vp9_dxva2
ffv1_vulkan             mpeg2_d3d12va           vp9_nvdec
h263_vaapi              mpeg2_dxva2             vp9_nvdec_cuarray
h264_d3d11va            mpeg2_nvdec             vp9_vaapi
h264_d3d11va2           mpeg2_nvdec_cuarray     vp9_vulkan
h264_d3d12va            mpeg2_vaapi             vvc_vaapi
h264_dxva2              mpeg4_nvdec             wmv3_d3d11va
h264_nvdec              mpeg4_nvdec_cuarray     wmv3_d3d11va2
h264_nvdec_cuarray      mpeg4_vaapi             wmv3_d3d12va
h264_vaapi              prores_raw_vulkan       wmv3_dxva2
h264_vulkan             prores_vulkan           wmv3_nvdec
hevc_d3d11va            vc1_d3d11va             wmv3_nvdec_cuarray
hevc_d3d11va2           vc1_d3d11va2            wmv3_vaapi
hevc_d3d12va            vc1_d3d12va
hevc_dxva2              vc1_dxva2

Enabled parsers:
aac                     dvdsub                  mpegaudio
aac_latm                evc                     mpegvideo
ac3                     ffv1                    opus
adx                     flac                    png
ahx                     ftr                     pnm
amr                     g723_1                  prores
apv                     g729                    prores_raw
av1                     gif                     qoi
avs2                    gsm                     rv34
avs3                    h261                    sbc
bmp                     h263                    sipr
cavsvideo               h264                    tak
cook                    hdr                     vc1
cri                     hevc                    vorbis
dca                     ipu                     vp3
dirac                   jpeg2000                vp8
dnxhd                   jpegxl                  vp9
dnxuc                   jpegxs                  vvc
dolby_e                 lcevc                   webp
dpx                     misc4                   xbm
dvaudio                 mjpeg                   xma
dvbsub                  mlp                     xwd
dvd_nav                 mpeg4video

Enabled demuxers:
aa                      idcin                   pcm_f64le
aac                     idf                     pcm_mulaw
aax                     iff                     pcm_s16be
ac3                     ifv                     pcm_s16le
ac4                     ilbc                    pcm_s24be
ace                     image2                  pcm_s24le
acm                     image2_alias_pix        pcm_s32be
act                     image2_brender_pix      pcm_s32le
adf                     image2pipe              pcm_s8
adp                     image_bmp_pipe          pcm_u16be
ads                     image_cri_pipe          pcm_u16le
adx                     image_dds_pipe          pcm_u24be
aea                     image_dpx_pipe          pcm_u24le
afc                     image_exr_pipe          pcm_u32be
aiff                    image_gem_pipe          pcm_u32le
aix                     image_gif_pipe          pcm_u8
alp                     image_hdr_pipe          pcm_vidc
amr                     image_j2k_pipe          pdv
amrnb                   image_jpeg_pipe         pjs
amrwb                   image_jpegls_pipe       pmp
anm                     image_jpegxl_pipe       pp_bnk
apac                    image_jpegxs_pipe       pva
apc                     image_pam_pipe          pvf
ape                     image_pbm_pipe          qcp
apm                     image_pcx_pipe          qoa
apng                    image_pfm_pipe          r3d
aptx                    image_pgm_pipe          rawvideo
aptx_hd                 image_pgmyuv_pipe       rcwt
apv                     image_pgx_pipe          realtext
aqtitle                 image_phm_pipe          redspark
argo_asf                image_photocd_pipe      rka
argo_brp                image_pictor_pipe       rl2
argo_cvg                image_png_pipe          rm
asf                     image_ppm_pipe          roq
asf_o                   image_psd_pipe          rpl
ass                     image_qdraw_pipe        rsd
ast                     image_qoi_pipe          rso
au                      image_sgi_pipe          rtp
av1                     image_sunrast_pipe      rtsp
avi                     image_svg_pipe          s337m
avisynth                image_tiff_pipe         sami
avr                     image_vbn_pipe          sap
avs                     image_webp_pipe         sbc
avs2                    image_xbm_pipe          sbg
avs3                    image_xpm_pipe          scc
bethsoftvid             image_xwd_pipe          scd
bfi                     imf                     sdns
bfstm                   ingenient               sdp
bink                    ipmovie                 sdr2
binka                   ipu                     sds
bintext                 ircam                   sdx
bit                     iss                     segafilm
bitpacked               iv8                     ser
bmv                     ivf                     sga
boa                     ivr                     shorten
bonk                    jacosub                 siff
brstm                   jpegxl_anim             simbiosis_imx
c93                     jv                      sln
caf                     kux                     smacker
cavsvideo               kvag                    smjpeg
cdg                     laf                     smush
cdxl                    lc3                     sol
cine                    libgme                  sox
codec2                  libmodplug              spdif
codec2raw               libopenmpt              srt
concat                  live_flv                stl
dash                    lmlm4                   str
data                    loas                    subviewer
daud                    lrc                     subviewer1
dcstr                   luodat                  sup
derf                    lvf                     svag
dfa                     lxf                     svs
dfpwm                   m4v                     swf
dhav                    matroska                tak
dirac                   mca                     tedcaptions
dnxhd                   mcc                     thp
dsf                     mgsts                   threedostr
dsicin                  microdvd                tiertexseq
dss                     mjpeg                   tmv
dts                     mjpeg_2000              truehd
dtshd                   mlp                     tta
dv                      mlv                     tty
dvbsub                  mm                      txd
dvbtxt                  mmf                     ty
dvdvideo                mods                    usm
dxa                     moflex                  v210
ea                      mov                     v210x
ea_cdata                mp3                     vag
eac3                    mpc                     vc1
epaf                    mpc8                    vc1t
evc                     mpegps                  vividas
ffmetadata              mpegts                  vivo
filmstrip               mpegtsraw               vmd
fits                    mpegvideo               vobsub
flac                    mpjpeg                  voc
flic                    mpl2                    vpk
flv                     mpsub                   vplayer
fourxm                  msf                     vqf
frm                     msnwc_tcp               vvc
fsb                     msp                     w64
fwse                    mtaf                    wady
g722                    mtv                     wav
g723_1                  musx                    wavarc
g726                    mv                      wc3
g726le                  mvi                     webm_dash_manifest
g728                    mvr                     webp_anim
g729                    mxf                     webvtt
gdv                     mxg                     wsaud
genh                    nc                      wsd
gif                     nistsphere              wsvqa
gsm                     nsp                     wtv
gxf                     nsv                     wv
h261                    nut                     wve
h263                    nuv                     xa
h264                    obu                     xbin
hca                     ogg                     xmd
hcom                    oma                     xmv
hevc                    osq                     xvag
hls                     paf                     xwma
hnm                     pcm_alaw                yop
hxvs                    pcm_f32be               yuv4mpegpipe
iamf                    pcm_f32le
ico                     pcm_f64be

Enabled muxers:
a64                     h263                    pcm_s16le
ac3                     h264                    pcm_s24be
ac4                     hash                    pcm_s24le
adts                    hds                     pcm_s32be
adx                     hevc                    pcm_s32le
aea                     hls                     pcm_s8
aiff                    iamf                    pcm_u16be
alp                     ico                     pcm_u16le
amr                     ilbc                    pcm_u24be
amv                     image2                  pcm_u24le
apm                     image2pipe              pcm_u32be
apng                    ipod                    pcm_u32le
aptx                    ircam                   pcm_u8
aptx_hd                 ismv                    pcm_vidc
apv                     iterm2                  pdv
argo_asf                ivf                     psp
argo_cvg                jacosub                 rawvideo
asf                     kvag                    rcwt
asf_stream              latm                    rm
ass                     lc3                     roq
ast                     lrc                     rso
au                      m4v                     rtp
avi                     matroska                rtp_mpegts
avif                    matroska_audio          rtsp
avm2                    mcc                     sap
avs2                    md5                     sbc
avs3                    microdvd                scc
bit                     mjpeg                   segafilm
caf                     mkvtimestamp_v2         segment
cavsvideo               mlp                     smjpeg
chromaprint             mmf                     smoothstreaming
codec2                  mov                     sox
codec2raw               mp2                     spdif
crc                     mp3                     spx
dash                    mp4                     srt
data                    mpeg1system             stream_segment
daud                    mpeg1vcd                streamhash
dfpwm                   mpeg1video              sup
dirac                   mpeg2dvd                swf
dnxhd                   mpeg2svcd               tee
dts                     mpeg2video              tg2
dv                      mpeg2vob                tgp
eac3                    mpegts                  truehd
evc                     mpjpeg                  tta
f4v                     mxf                     ttml
ffmetadata              mxf_d10                 uncodedframecrc
fifo                    mxf_opatom              vc1
filmstrip               null                    vc1t
fits                    nut                     voc
flac                    obu                     vvc
flv                     oga                     w64
framecrc                ogg                     wav
framehash               ogv                     webm
framemd5                oma                     webm_chunk
g722                    opus                    webm_dash_manifest
g723_1                  pcm_alaw                webp
g726                    pcm_f32be               webvtt
g726le                  pcm_f32le               whip
gif                     pcm_f64be               wsaud
gsm                     pcm_f64le               wtv
gxf                     pcm_mulaw               wv
h261                    pcm_s16be               yuv4mpegpipe

Enabled protocols:
async                   http                    rtmp
bluray                  httpproxy               rtmpe
cache                   https                   rtmps
concat                  icecast                 rtmpt
concatf                 ipfs_gateway            rtmpte
crypto                  ipns_gateway            rtmpts
data                    librist                 rtp
dtls                    libsrt                  srtp
fd                      libssh                  subfile
ffrtmpcrypt             libzmq                  tcp
ffrtmphttp              md5                     tee
file                    mmsh                    tls
ftp                     mmst                    udp
gopher                  pipe                    udplite
gophers                 prompeg

Enabled filters:
a3dscope                dedot                   perspective
aap                     deesser                 phase
abench                  deflate                 photosensitivity
abitscope               deflicker               pixdesctest
acompressor             deinterlace_d3d12       pixelize
acontrast               deinterlace_qsv         pixscope
acopy                   deinterlace_vaapi       pp7
acrossfade              dejudder                premultiply
acrossover              delogo                  premultiply_dynamic
acrusher                denoise_vaapi           prewitt
acue                    deshake                 prewitt_opencl
addroi                  deshake_opencl          procamp_vaapi
adeclick                despill                 program_opencl
adeclip                 detelecine              pseudocolor
adecorrelate            dialoguenhance          psnr
adelay                  dilation                pullup
adenorm                 dilation_opencl         qp
aderivative             displace                qrencode
adrawgraph              doubleweave             qrencodesrc
adrc                    drawbox                 quirc
adynamicequalizer       drawbox_vaapi           random
adynamicsmooth          drawgraph               readeia608
aecho                   drawgrid                readvitc
aemphasis               drawtext                realtime
aeval                   drawvg                  remap
aevalsrc                drmeter                 remap_opencl
aexciter                dynaudnorm              removegrain
afade                   earwax                  removelogo
afdelaysrc              ebur128                 repeatfields
afftdn                  edgedetect              replaygain
afftfilt                elbg                    reverse
afir                    entropy                 rgbashift
afireqsrc               epx                     rgbtestsrc
afirsrc                 eq                      roberts
aformat                 equalizer               roberts_opencl
afreqshift              erosion                 rotate
afwtdn                  erosion_opencl          rubberband
agate                   estdif                  sab
agraphmonitor           exposure                scale
ahistogram              extractplanes           scale2ref
aiir                    extrastereo             scale_cuda
aintegral               fade                    scale_d3d11
ainterleave             feedback                scale_d3d12
alatency                fftdnoiz                scale_qsv
alimiter                fftfilt                 scale_vaapi
allpass                 field                   scale_vulkan
allrgb                  fieldhint               scdet
allyuv                  fieldmatch              scdet_vulkan
aloop                   fieldorder              scharr
alphaextract            fillborders             scroll
alphamerge              find_rect               segment
amerge                  firequalizer            select
ametadata               flanger                 selectivecolor
amf_capture             flip_vulkan             sendcmd
amix                    flite                   separatefields
amovie                  floodfill               setdar
amplify                 format                  setfield
amultiply               fps                     setparams
anequalizer             framepack               setpts
anlmdn                  framerate               setrange
anlmf                   framestep               setsar
anlms                   frc_amf                 settb
anoisesrc               freezedetect            sharpness_vaapi
anull                   freezeframes            shear
anullsink               frei0r                  showcqt
anullsrc                frei0r_src              showcwt
apad                    fspp                    showfreqs
aperms                  fsync                   showinfo
aphasemeter             gblur                   showpalette
aphaser                 gblur_vulkan            showspatial
aphaseshift             geq                     showspectrum
apsnr                   gfxcapture              showspectrumpic
apsyclip                gradfun                 showvolume
apulsator               gradients               showwaves
arealtime               graphmonitor            showwavespic
aresample               grayworld               shuffleframes
areverse                greyedge                shufflepixels
arls                    guided                  shuffleplanes
arnndn                  haas                    sidechaincompress
asdr                    haldclut                sidechaingate
asegment                haldclutsrc             sidedata
aselect                 hdcd                    sierpinski
asendcmd                headphone               signalstats
asetnsamples            hflip                   signature
asetpts                 hflip_vulkan            silencedetect
asetrate                highpass                silenceremove
asettb                  highshelf               sinc
ashowinfo               hilbert                 sine
asidedata               histeq                  siti
asisdr                  histogram               smartblur
asoftclip               hqdn3d                  smptebars
aspectralstats          hqx                     smptehdbars
asplit                  hstack                  sobel
ass                     hstack_qsv              sobel_opencl
astats                  hstack_vaapi            sofalizer
astreamselect           hsvhold                 spectrumsynth
asubboost               hsvkey                  speechnorm
asubcut                 hue                     split
asupercut               huesaturation           spp
asuperpass              hwdownload              sr_amf
asuperstop              hwmap                   ssim
atadenoise              hwupload                ssim360
atempo                  hwupload_cuda           stereo3d
atilt                   hysteresis              stereotools
atrim                   iccdetect               stereowiden
avectorscope            iccgen                  streamselect
avgblur                 identity                subtitles
avgblur_opencl          idet                    super2xsai
avgblur_vulkan          il                      superequalizer
avsynctest              inflate                 surround
axcorrelate             interlace               swaprect
azmq                    interlace_vulkan        swapuv
backgroundkey           interleave              tblend
bandpass                join                    telecine
bandreject              kerndeint               testsrc
bass                    kirsch                  testsrc2
bbox                    ladspa                  thistogram
bench                   lagfun                  threshold
bilateral               latency                 thumbnail
bilateral_cuda          latticepal              thumbnail_cuda
biquad                  lenscorrection          tile
bitplanenoise           lensfun                 tiltandshift
blackdetect             libplacebo              tiltshelf
blackdetect_vulkan      libvmaf                 tinterlace
blackframe              life                    tlut2
blend                   limitdiff               tmedian
blend_vulkan            limiter                 tmidequalizer
blockdetect             loop                    tmix
blurdetect              loudnorm                tonemap
bm3d                    lowpass                 tonemap_opencl
boxblur                 lowshelf                tonemap_vaapi
boxblur_opencl          lumakey                 tpad
bs2b                    lut                     transpose
bwdif                   lut1d                   transpose_cuda
bwdif_cuda              lut2                    transpose_opencl
bwdif_vulkan            lut3d                   transpose_vaapi
cas                     lutrgb                  transpose_vulkan
ccrepack                lutyuv                  treble
cellauto                mandelbrot              tremolo
channelmap              maskedclamp             trim
channelsplit            maskedmax               unpremultiply
chorus                  maskedmerge             unsharp
chromaber_vulkan        maskedmin               unsharp_opencl
chromahold              maskedthreshold         untile
chromakey               maskfun                 uspp
chromakey_cuda          mcdeint                 v360
chromanr                mcompand                v360_vulkan
chromashift             median                  vaguedenoiser
ciescope                mergeplanes             varblur
codecview               mestimate               vectorscope
color                   mestimate_d3d12         vflip
color_vulkan            metadata                vflip_vulkan
colorbalance            midequalizer            vfrdet
colorchannelmixer       minterpolate            vibrance
colorchart              mix                     vibrato
colorcontrast           monochrome              vidstabdetect
colorcorrect            morpho                  vidstabtransform
colordetect             movie                   vif
colorhold               mpdecimate              vignette
colorize                mptestsrc               virtualbass
colorkey                msad                    vmafmotion
colorkey_opencl         multiply                volume
colorlevels             negate                  volumedetect
colormap                nlmeans                 vpp_amf
colormatrix             nlmeans_opencl          vpp_qsv
colorspace              nlmeans_vulkan          vqe_amf
colorspace_cuda         nnedi                   vstack
colorspectrum           noformat                vstack_qsv
colortemperature        noise                   vstack_vaapi
compand                 normalize               w3fdif
compensationdelay       null                    waveform
concat                  nullsink                weave
convolution             nullsrc                 whisper
convolution_opencl      openclsrc               xbr
convolve                oscilloscope            xcorrelate
copy                    overlay                 xfade
corr                    overlay_cuda            xfade_opencl
cover_rect              overlay_opencl          xfade_vulkan
crop                    overlay_qsv             xmedian
cropdetect              overlay_vaapi           xpsnr
crossfeed               overlay_vulkan          xstack
crystalizer             owdenoise               xstack_qsv
cue                     pad                     xstack_vaapi
curves                  pad_cuda                yadif
datascope               pad_opencl              yadif_cuda
dblur                   pad_vaapi               yaepblur
dcshift                 pal100bars              yuvtestsrc
dctdnoiz                pal75bars               zmq
ddagrab                 palettegen              zoneplate
deband                  paletteuse              zoompan
deblock                 pan                     zscale
decimate                perlin
deconvolve              perms

Enabled bsfs:
aac_adtstoasc           h264_metadata           pcm_rechunk
ahx_to_mp2              h264_mp4toannexb        pgs_frame_merge
apv_metadata            h264_redundant_pps      prores_metadata
av1_frame_merge         hapqa_extract           remove_extradata
av1_frame_split         hevc_metadata           setts
av1_metadata            hevc_mp4toannexb        showinfo
chomp                   imx_dump_header         smpte436m_to_eia608
dca_core                lcevc_merge             text2movsub
dovi_rpu                lcevc_metadata          trace_headers
dovi_split              media100_to_mjpegb      truehd_core
dts2pts                 mjpeg2jpeg              vp9_metadata
dump_extradata          mjpega_dump_header      vp9_raw_reorder
dv_error_marker         mov2textsub             vp9_superframe
eac3_core               mpeg2_metadata          vp9_superframe_split
eia608_to_smpte436m     mpeg4_unpack_bframes    vvc_metadata
evc_frame_merge         noise                   vvc_mp4toannexb
extract_extradata       null
filter_units            opus_metadata

Enabled indevs:
dshow                   lavfi                   openal
gdigrab                 libcdio                 vfwcap

Enabled outdevs:
caca

git-full external libraries' versions: 

AMF v1.5.2-2-gc35f613
aom v3.14.1-124-g18c52422b8
aribcaption 1.1.1
AviSynthPlus v3.7.5-342-gcfdaf8eb
bs2b 3.1.0
cairo 1.18.5
chromaprint 1.6.0
codec2 1.2.0-108-g310777b1
dav1d 1.5.4
davs2 1.7-1-gb41cf11
dvdnav 7.0.0-14-ge0c02b9
dvdread 7.1.0-13-g8e43bfe
ffnvcodec n13.1.15.0-1-geddcea9
flite v2.2-55-g6c9f20d
frei0r v3.2.3
gsm 1.0.24
ladspa-sdk 1.17
lame 3.100
lc3 1.1.3
lcms2 2.16
lensfun v0.3.95-1986-g698a39ee
libcdio-paranoia 10.2
libgme 0.6.6
libilbc v3.0.4-346-g6adb26d4a4
libjxl v0.12-snapshot-2-g196a43d9
libopencore-amrnb 0.1.6
libopencore-amrwb 0.1.6
libplacebo v7.360.0-105-ga7a18af
libsoxr 0.1.3
libssh 0.12.0
libtheora v1.2.0
libwebp v1.6.0-195-g733c91e
openal-soft latest
openapv v0.3.0.0-6-g45175b2
openmpt libopenmpt-0.6.28-36-g73119913
opus v1.6.1-50-g3da9f7a6
qrencode 4.1.1
quirc 1.2
rav1e p20250624-3-g564ae3b
rist 0.2.19
rubberband v4.0.0
SDL release-2.32.0-226-g76847b46b
shaderc v2026.3-1-ge688680
shine 3.1.1
snappy 1.2.2
speex Speex-1.2.1-51-g0589522
srt v1.5.5-9-gc39196c
SVT-AV1 v4.2.0-15-g8b1f9a0dc
SVT-JPEG-XS v0.9.0-66-g0727a05
twolame 0.4.0
uavs3d v1.1-50-g0e20d2c
VAAPI 2.25.0.
vidstab v1.1.1-24-g92bc0b0
vmaf v3.2.0-7-g78e11b52
vo-amrwbenc 0.1.3
vorbis v1.3.7-36-ge3c9861f
VPL 2.17
vpx v1.16.0-164-g1ef0fcd4b
vulkan-loader v1.4.357
vvenc v1.14.0-155-g9c979c5
whisper.cpp 1.9.1
x264 v0.165.3223
x265 4.2-68-gef0259e
xavs2 1.4
xevd 0.5.0
xeve 0.5.1
xvid v1.3.7
zeromq 4.3.5
zimg release-3.0.6-251-g274b46e
zvbi v0.2.44-7-g2e15952


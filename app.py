import os, re, shutil, subprocess, tempfile, textwrap, wave
from pathlib import Path
import streamlit as st

st.set_page_config(page_title='Myanmar AI Movie Recap Studio', page_icon='🎬', layout='wide')
st.title('🎬 Myanmar AI Movie Recap Studio')
st.caption('Free local MVP • Your files stay on your computer • Authorized footage only')
st.info('This version can make a video from your own MP4, Burmese script, narration audio and subtitles. Full automatic movie understanding and Burmese TTS require additional models/services.')

if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
    st.error('FFmpeg and ffprobe are required. Install FFmpeg before running the app.')
    st.stop()

def run(cmd):
    p=subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode: raise RuntimeError((p.stderr or p.stdout)[-3000:])
    return p.stdout

def duration(p):
    try: return float(run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(p)]).strip())
    except Exception: return 0.0

def stamp(t):
    ms=int(round(t*1000)); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); s,ms=divmod(ms,1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

def srt_for(text, seconds):
    lines=[x.strip() for x in re.split(r'(?<=[။!?\n])\s*', text) if x.strip()]
    if not lines: lines=[text.strip()]
    # Time is estimated, not word-aligned; adjust in editor before publishing.
    weights=[max(1,len(x)) for x in lines]; total=sum(weights); t=0; out=[]
    for i,(line,w) in enumerate(zip(lines,weights),1):
        nxt=seconds if i==len(lines) else t+seconds*w/total
        out.append(f'{i}\n{stamp(t)} --> {stamp(nxt)}\n{line}\n')
        t=nxt
    return '\n'.join(out)

with st.sidebar:
    st.header('Project settings')
    title=st.text_input('Project title','My Burmese Movie Recap')
    fmt=st.selectbox('Format',['YouTube 16:9','TikTok 9:16'])
    st.caption('Processing can be slow on ordinary computers.')

video=st.file_uploader('1. Upload an MP4 you own or are permitted to edit',type=['mp4'])
transcript=st.text_area('2. Paste transcript / story notes (optional)',height=120,placeholder='ဇာတ်လမ်းအကြောင်းအရာကို ဒီမှာရေးပါ...')
script=st.text_area('3. Burmese recap narration script (editable)',value=transcript,height=220,placeholder='မြန်မာလို ပြောမယ့် ဇာတ်လမ်းအကျဉ်းချုပ်...')
voice=st.file_uploader('4. Upload Burmese narration (MP3, WAV, M4A)',type=['mp3','wav','m4a'])
st.caption('Record your own narration or use an authorized Burmese TTS service. The app does not pretend to generate an AI voice.')

if 'srt' not in st.session_state: st.session_state.srt=''
if st.button('Generate estimated subtitles from script'):
    if not script.strip(): st.warning('Enter a Burmese script first.')
    else:
        length=60
        if voice:
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/voice.name;p.write_bytes(voice.getvalue());length=duration(p) or 60
        st.session_state.srt=srt_for(script,length)
        st.success('Estimated subtitle timings generated. Review before export.')
srt=st.text_area('5. Subtitle editor (SRT)',height=170,key='srt')
if srt.strip(): st.download_button('Download SRT',srt.encode('utf-8'),'recap.srt','application/x-subrip')
if script.strip(): st.download_button('Download script TXT',script.encode('utf-8'),'recap_script.txt','text/plain')

st.subheader('6. Render video')
st.caption('Video is trimmed or looped to narration length; automatic semantic scene matching is not implemented.')
if st.button('🎞️ Render MP4',type='primary'):
    if not video or not voice: st.error('Upload both an authorized MP4 and a narration audio file.')
    elif not script.strip(): st.error('Enter a narration script.')
    else:
        try:
            with st.spinner('Rendering MP4 — please wait...'):
                d=Path(tempfile.mkdtemp(prefix='mmrecap_'))
                vp=d/'input.mp4'; vp.write_bytes(video.getvalue())
                ap=d/('voice'+Path(voice.name).suffix.lower()); ap.write_bytes(voice.getvalue())
                vd=duration(vp); ad=duration(ap)
                if vd<=0 or ad<=0: raise RuntimeError('Unable to read video or audio duration.')
                out=d/'recap.mp4'
                width,height=(1920,1080) if fmt.startswith('YouTube') else (1080,1920)
                vf=f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1'
                if srt.strip():
                    sub=d/'subtitles.srt';sub.write_text(srt,encoding='utf-8')
                    # FFmpeg filter paths must be escaped; temporary path contains no special characters.
                    vf+=f",subtitles={sub.as_posix()}:force_style='FontName=Noto Sans Myanmar,FontSize=22,Outline=2,Alignment=2'"
                cmd=['ffmpeg','-y','-stream_loop','-1','-i',str(vp),'-i',str(ap),'-map','0:v:0','-map','1:a:0','-vf',vf,'-t',str(ad),'-c:v','libx264','-preset','veryfast','-crf','25','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-movflags','+faststart',str(out)]
                run(cmd)
                st.session_state.rendered=out.read_bytes()
            st.success('MP4 rendered successfully!')
        except Exception as e: st.error(f'Render failed: {e}')
if st.session_state.get('rendered'):
    st.video(st.session_state.rendered)
    st.download_button('⬇️ Download final MP4',st.session_state.rendered,'myanmar_movie_recap.mp4','video/mp4')
st.divider()
st.caption('Privacy: local app. Large files consume memory. This prototype is intended for short clips first; long movies need disk-based uploads and background workers.')

#!/usr/bin/env python3
import json, os, subprocess, math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
OUT, WORK = ROOT / "output", ROOT / "work"
OUT.mkdir(exist_ok=True)
WORK.mkdir(exist_ok=True)

def run(args):
    subprocess.run(args, check=True)

def get_font(size, bold=False):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(path, size)

def lines_for(draw, text, fnt, width):
    result, current = [], ""
    for word in text.split():
        trial = (current + " " + word).strip()
        if draw.textbbox((0, 0), trial, font=fnt)[2] <= width:
            current = trial
        else:
            if current: result.append(current)
            current = word
    if current: result.append(current)
    return result

def make_slide(i, scene, count):
    w, h = 1080, 1920
    im = Image.new("RGB", (w, h), (8, 14, 25))
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / h
        d.line((0, y, w, y), fill=(int(8+5*t), int(14+10*t), int(25+18*t)))
    d.ellipse((620, -260, 1320, 440), outline=(28, 65, 94), width=5)
    d.ellipse((-330, 1320, 430, 2080), outline=(28, 65, 94), width=5)
    d.rectangle((70, 90, 1010, 100), fill=(0, 205, 255))
    d.text((76, 130), "60 SECONDS MOTORS", font=get_font(38, True), fill=(0, 205, 255))
    d.text((76, 195), "MECCANICA  |  %02d/%02d" % (i+1, count), font=get_font(25, True), fill=(150, 170, 190))
    title_font = get_font(76, True)
    y = 470
    for line in lines_for(d, scene["title"].upper(), title_font, 900):
        d.text((76, y), line, font=title_font, fill=(255, 255, 255))
        y += 100
    d.rounded_rectangle((76, y+30, 250, y+43), radius=6, fill=(0, 205, 255))
    body_font = get_font(47)
    y += 115
    for line in lines_for(d, scene["text"], body_font, 900):
        d.text((76, y), line, font=body_font, fill=(215, 225, 238))
        y += 68
    cx, cy = 850, 1510
    d.arc((cx-170, cy-170, cx+170, cy+170), 190, 350, fill=(0, 205, 255), width=13)
    for a in range(195, 350, 15):
        r1, r2 = 145, 165
        x1, y1 = cx+int(r1*math.cos(math.radians(a))), cy+int(r1*math.sin(math.radians(a)))
        x2, y2 = cx+int(r2*math.cos(math.radians(a))), cy+int(r2*math.sin(math.radians(a)))
        d.line((x1, y1, x2, y2), fill=(150, 180, 205), width=5)
    d.text((76, 1780), "SEGUI 60 SECONDS MOTORS", font=get_font(28, True), fill=(0, 205, 255))
    path = WORK / ("slide_%02d.png" % i)
    im.save(path)
    return path

def main():
    data = json.loads((ROOT / "content.json").read_text(encoding="utf-8"))
    scenes = data["scenes"]
    narration = " ".join(s["voice"] for s in scenes)
    (WORK / "narration.txt").write_text(narration, encoding="utf-8")
    run(["espeak-ng", "-v", "it", "-s", "158", "-p", "38", "-a", "175", "-f", str(WORK/"narration.txt"), "-w", str(WORK/"voice.wav")])
    duration = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(WORK/"voice.wav")], text=True).strip())
    weights = [max(1, len(s["voice"].split())) for s in scenes]
    durations = [duration*x/sum(weights) for x in weights]
    concat = []
    for i, scene in enumerate(scenes):
        img = make_slide(i, scene, len(scenes))
        clip = WORK / ("clip_%02d.mp4" % i)
        run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(img), "-t", "%.3f" % durations[i], "-vf", "scale=1080:1920,zoompan=z='min(zoom+0.0005,1.04)':d=1:s=1080x1920:fps=30,format=yuv420p", "-r", "30", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "25", str(clip)])
        concat.append("file '%s'" % clip.as_posix())
    concat_file = WORK / "concat.txt"
    concat_file.write_text("\n".join(concat), encoding="utf-8")
    silent = WORK / "silent.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(silent)])
    def stamp(t):
        ms = int(round(t*1000))
        hh, ms = divmod(ms, 3600000)
        mm, ms = divmod(ms, 60000)
        ss, ms = divmod(ms, 1000)
        return "%02d:%02d:%02d,%03d" % (hh, mm, ss, ms)
    entries, start = [], 0.0
    for i, (scene, sec) in enumerate(zip(scenes, durations), 1):
        end = start + sec
        entries.append("%d\n%s --> %s\n%s\n" % (i, stamp(start), stamp(end), scene["voice"]))
        start = end
    srt = OUT / "shorts.srt"
    srt.write_text("\n".join(entries), encoding="utf-8")
    final = OUT / "60-seconds-motors.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(WORK/"voice.wav"), "-vf", "subtitles=%s:force_style='FontName=DejaVu Sans,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=150'" % srt.as_posix(), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(final)])
    print("Creato:", final)

if __name__ == "__main__":
    main()

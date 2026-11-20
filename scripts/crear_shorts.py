"""
Crea shorts verticales (9:16) de GTA 6 a partir de clips propios.

Para cada vídeo en clips/:
  - Si existe guiones/<mismo_nombre>.txt -> genera voz en off en español (edge-tts)
    y subtítulos sincronizados palabra a palabra.
  - Recorta el clip a formato vertical 1080x1920, máximo 59 s.
  - Baja el audio original del juego y mezcla la voz.
  - Quema los subtítulos en el vídeo.
Resultado: shorts/<nombre>_short.mp4

Uso:
  python scripts/crear_shorts.py
  python scripts/crear_shorts.py --voz es-MX-JorgeNeural --duracion-max 45
"""

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CLIPS = RAIZ / "clips"
GUIONES = RAIZ / "guiones"
SALIDA = RAIZ / "shorts"
EXTENSIONES = {".mp4", ".mov", ".mkv", ".webm", ".avi"}

# Estilo de subtítulos: grandes, amarillos, borde negro, centrados un poco abajo
ESTILO_SUBS = (
    "FontName=Arial,FontSize=16,Bold=1,PrimaryColour=&H0000FFFF,"
    "OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,"
    "Alignment=2,MarginV=70"
)


# ---------------------------------------------------------------- utilidades
def duracion(ruta: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(ruta)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


def tiene_audio(ruta: Path) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(ruta)],
        capture_output=True, text=True,
    ).stdout
    return bool(out.strip())


def tiempo_srt(seg: float) -> str:
    ms = int(round(seg * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ---------------------------------------------------------------- voz + subs
async def generar_voz(texto: str, voz: str, mp3: Path, srt: Path,
                      palabras_por_linea: int) -> None:
    import edge_tts  # se instala en GitHub Actions (requirements.txt)

    com = edge_tts.Communicate(texto, voz, rate="+8%", boundary="WordBoundary")
    palabras = []  # (inicio, fin, texto)
    with open(mp3, "wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                ini = chunk["offset"] / 1e7
                fin = ini + chunk["duration"] / 1e7
                palabras.append((ini, fin, chunk["text"]))

    lineas = []
    for i in range(0, len(palabras), palabras_por_linea):
        grupo = palabras[i:i + palabras_por_linea]
        texto_linea = " ".join(p[2] for p in grupo).upper()
        lineas.append((grupo[0][0], grupo[-1][1], texto_linea))

    with open(srt, "w", encoding="utf-8") as f:
        for n, (ini, fin, txt) in enumerate(lineas, 1):
            f.write(f"{n}\n{tiempo_srt(ini)} --> {tiempo_srt(fin)}\n{txt}\n\n")


# ---------------------------------------------------------------- montaje
def montar(clip: Path, destino: Path, dur: float, voz_mp3: Path | None,
           srt: Path | None, tmp: Path, inicio: float) -> None:
    filtro_video = (
        "scale=-2:1920,crop=1080:1920,setsar=1"  # vertical centrado
    )
    if srt:
        filtro_video += f",subtitles={srt.name}:force_style='{ESTILO_SUBS}'"

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{inicio:.2f}", "-i", str(clip)]
    audio_juego = tiene_audio(clip)

    if voz_mp3:
        cmd += ["-i", str(voz_mp3)]
        if audio_juego:
            filtro = (
                f"[0:v]{filtro_video}[v];"
                "[0:a]volume=0.15[juego];"
                "[1:a]volume=1.6[voz];"
                "[juego][voz]amix=inputs=2:duration=longest:normalize=0[a]"
            )
        else:
            filtro = f"[0:v]{filtro_video}[v];[1:a]volume=1.6[a]"
        cmd += ["-filter_complex", filtro, "-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-vf", filtro_video]
        if audio_juego:
            cmd += ["-map", "0:v:0", "-map", "0:a:0"]

    cmd += [
        "-t", f"{dur:.2f}",
        "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", str(destino),
    ]
    subprocess.run(cmd, check=True, cwd=tmp)


# ---------------------------------------------------------------- principal
def procesar(clip: Path, args) -> None:
    nombre = clip.stem
    destino = SALIDA / f"{nombre}_short.mp4"
    guion = GUIONES / f"{nombre}.txt"
    dur_clip = duracion(clip)
    inicio = min(args.inicio, max(dur_clip - 1, 0))

    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        voz_mp3 = srt = None

        if guion.exists() and guion.read_text(encoding="utf-8").strip():
            texto = guion.read_text(encoding="utf-8").strip()
            voz_mp3, srt = tmp / "voz.mp3", tmp / "subs.srt"
            print(f"  · Generando voz ({args.voz})...")
            asyncio.run(generar_voz(texto, args.voz, voz_mp3, srt,
                                    args.palabras_por_linea))
            dur = duracion(voz_mp3) + 0.6
        else:
            print("  · Sin guion: short sin voz ni subtítulos")
            dur = dur_clip - inicio

        dur = min(dur, dur_clip - inicio, args.duracion_max)
        if voz_mp3 and duracion(voz_mp3) > dur:
            print(f"  ! Aviso: la voz dura más que el clip; se cortará a {dur:.1f}s")

        print(f"  · Montando short de {dur:.1f}s...")
        montar(clip, destino, dur, voz_mp3, srt, tmp, inicio)
    print(f"  ✓ {destino.relative_to(RAIZ)}")


def main() -> None:
    p = argparse.ArgumentParser(description="Clips de GTA 6 -> shorts verticales")
    p.add_argument("--voz", default="es-ES-AlvaroNeural",
                   help="Voz de edge-tts (ej. es-MX-JorgeNeural, es-ES-ElviraNeural)")
    p.add_argument("--duracion-max", type=float, default=59.0)
    p.add_argument("--inicio", type=float, default=0.0,
                   help="Segundo del clip desde el que empezar")
    p.add_argument("--palabras-por-linea", type=int, default=3)
    p.add_argument("--solo", help="Procesar solo este archivo de clips/")
    args = p.parse_args()

    SALIDA.mkdir(exist_ok=True)
    clips = sorted(c for c in CLIPS.glob("*") if c.suffix.lower() in EXTENSIONES)
    if args.solo:
        clips = [c for c in clips if c.name == args.solo]
    if not clips:
        print("No hay clips en la carpeta clips/. Sube alguno y vuelve a ejecutar.")
        return

    fallos = 0
    for clip in clips:
        print(f"\n▶ {clip.name}")
        try:
            procesar(clip, args)
        except Exception as e:  # sigue con el resto de clips
            fallos += 1
            print(f"  ✗ Error con {clip.name}: {e}")
    print(f"\nListo: {len(clips) - fallos} short(s) creados, {fallos} con error.")
    sys.exit(1 if fallos == len(clips) else 0)


if __name__ == "__main__":
    main()

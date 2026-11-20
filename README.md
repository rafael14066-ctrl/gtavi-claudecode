# gtavi-claudecode

GitHub convierte tus clips de GTA 6 en **shorts verticales (9:16)** con **voz en off en español** y **subtítulos**, listos para YouTube Shorts o TikTok.

## Cómo se usa

1. Sube un clip a la carpeta `clips/`, por ejemplo `clips/persecucion.mp4`.
2. (Opcional) Escribe lo que dirá la voz en `guiones/persecucion.txt`. Tiene que llamarse **igual que el clip**.
3. Haz commit y push. GitHub Actions se ejecuta solo.
4. Entra en la pestaña **Actions**, abre la última ejecución y descarga **shorts-gta6** (un .zip con tus vídeos).

Si un clip no tiene guion, sale el short vertical sin voz y sin subtítulos.

## Ejecutarlo a mano con otras opciones

En **Actions → Crear shorts de GTA 6 → Run workflow** puedes elegir:
- **voz**: `es-ES-AlvaroNeural` (España, hombre), `es-ES-ElviraNeural` (España, mujer), `es-MX-JorgeNeural` (México, hombre), `es-MX-DaliaNeural` (México, mujer)
- **duracion_max**: segundos máximos (por defecto 59)
- **inicio**: segundo del clip desde el que empieza

## En tu PC (opcional)

Necesitas Python y ffmpeg:

```
pip install -r requirements.txt
python scripts/crear_shorts.py
```

## Consejos

- GitHub no acepta archivos de más de **100 MB**. Con clips más grandes, recórtalos antes o activa Git LFS (`git lfs track "clips/*.mp4"`).
- Los guiones de entre 25 y 45 s (unas 70-120 palabras) funcionan mejor. Empieza con un gancho fuerte en la primera frase.
- Usa clips que hayas grabado tú. Así el contenido es tuyo y YouTube no lo marca como reutilizado.

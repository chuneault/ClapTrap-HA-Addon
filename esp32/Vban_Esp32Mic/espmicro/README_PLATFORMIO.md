# PlatformIO dans VS Code

Ce dossier peut maintenant etre ouvert directement comme projet PlatformIO dans VS Code.

## Utilisation

1. Installe l'extension `PlatformIO IDE` dans VS Code.
2. Ouvre le dossier `esp32/Vban_Esp32Mic/espmicro`.
3. Laisse le fichier `espmicro.ino` tel quel: PlatformIO compile ce dossier avec `src_dir = .`.
4. Choisis l'environnement:
   - `esp32dev` pour ta carte ESP32 actuelle
   - `esp32-s3-devkitc-1` pour tester un ESP32-S3 compatible
5. Lance `Build`, `Upload`, puis `Monitor`.

## Notes

- Ton sketch `.ino` est conserve, il n'a pas besoin d'etre converti en `.cpp`.
- Si la carte ESP32-S3 exacte differe, il faudra peut-etre ajuster `board = ...` dans `platformio.ini`.
- Les pins I2S de ton sketch actuel sont conservees telles quelles. Si la nouvelle carte n'utilise pas le meme cablage, il faudra les adapter dans `espmicro.ino`.

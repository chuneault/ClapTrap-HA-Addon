# ESP32 Notes

## Montage valide

Carte testee avec succes:
- `Freenove ESP32-S3 WROOM`

Micro teste avec succes:
- `INMP441` (micro I2S)

Branchement valide sur le `ESP32-S3`:

```text
INMP441    -> ESP32-S3
VDD        -> 3V3
GND        -> GND
SCK / BCLK -> GPIO3
WS / LRCL  -> GPIO14
SD / DOUT  -> GPIO46
L/R        -> GND
```

Notes:
- Un seul `GND` sur la carte suffit.
- `L/R -> GND` donne ici le bon canal lu par le sketch.
- Si besoin, dedoubler le `GND` avec une breadboard ou deux fils sur la meme masse.

## Sketch

Le sketch utilise:
- ancien `ESP32`: `BCK=26`, `WS=25`, `SD=33`
- `ESP32-S3`: `BCK=3`, `WS=14`, `SD=46`

Fichier principal:
- [Vban_Esp32Mic/espmicro/espmicro.ino](/Users/chuneault/projets/ClapTrap-HA-Addon/esp32/Vban_Esp32Mic/espmicro/espmicro.ino)

Le montage valide sur `ESP32-S3` lit bien le micro sur le `slot 0`.

## Exemple fonctionnel

Exemple complet valide pour ton montage `Freenove ESP32-S3 + INMP441`:

```cpp
auto cfg_i2s = i2sStream.defaultConfig(RX_MODE);
cfg_i2s.sample_rate = 16000;
cfg_i2s.bits_per_sample = 32;
cfg_i2s.channels = 2;
cfg_i2s.use_apll = false;
cfg_i2s.auto_clear = true;
cfg_i2s.pin_bck = 3;
cfg_i2s.pin_ws = 14;
cfg_i2s.pin_data = 46;
```

Avec ce cablage physique:

```text
INMP441 VDD   -> ESP32-S3 3V3
INMP441 GND   -> ESP32-S3 GND
INMP441 SCK   -> ESP32-S3 GPIO3
INMP441 WS    -> ESP32-S3 GPIO14
INMP441 SD    -> ESP32-S3 GPIO46
INMP441 L/R   -> ESP32-S3 GND
```

Lecture du bon canal dans la boucle:

```cpp
for (int i = 0; i < samplesRead - 1; i += 2) {
  int32_t s16 = inBuffer[i] >> 16;
  outBuffer[outCount++] = (int16_t)s16;
}
```

Ce montage a ete valide avec:
- `bytesRead=1024`
- `peak` non nul
- audio transmis correctement en `VBAN`

## Flash

Avec `PlatformIO`:

```bash
cd /Users/chuneault/projets/ClapTrap-HA-Addon/esp32/Vban_Esp32Mic/espmicro
platformio run -e esp32-s3-devkitc-1 -t upload
```

Si la carte n'entre pas automatiquement en mode flash:
1. Maintenir `BOOT`
2. Appuyer sur `EN/RST`
3. Relacher `EN/RST`
4. Relacher `BOOT`

Si le sketch ne demarre pas apres upload:
- appuyer une fois sur `EN/RST`

## Debug utile

Quand tout va bien dans le moniteur serie:
- `I2S begin: OK`
- `bytesRead=1024`
- `peak` varie quand on parle, siffle ou clap

Symptomes rencontres:
- `bytesRead=1024` avec `peak=0`: bus I2S actif mais signal micro nul
- cause la plus probable: fil `SD/DOUT` mauvais, pin micro lue a l'envers, ou alim micro incorrecte

## Resultats constates

Avec le `ESP32-S3`, le projet est beaucoup plus reactif qu'avec l'ancien `ESP32`.

Constats:
- latence percue beaucoup plus faible
- flux `VBAN` plus stable
- detection `Speech` et `Whistling` tres bonne
- frappe clavier reconnue plus facilement comme `Typewriter` que `Computer keyboard`

Dans `ClapTrap`, `Typewriter` est maintenant traite comme la meme intention que `Computer keyboard`.

## Home Assistant

Webhook de test utilise:
- `claptrap_bureau_9f3k2x7m`

Exemple simple:
- `clap_detected` -> `light.toggle`

Remarque:
- compter deux claps rapides via les webhooks n'est pas toujours fiable, car `YAMNet` peut interpreter une courte sequence comme `Clapping` plutot que deux evenements distincts.

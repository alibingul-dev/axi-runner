#!/usr/bin/env bash
# ffmpeg kurulumu: apt 2 deneme -> BtbN (GitHub) -> johnvansickle. Paket tam inmeden açılmaz.
set -u
command -v ffmpeg >/dev/null && { ffmpeg -version | head -1; exit 0; }
for i in 1 2; do
  timeout 180 sudo apt-get install -y -qq --no-install-recommends ffmpeg && exit 0
  echo "apt deneme $i başarısız"; sleep 10
done
for url in \
  https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz \
  https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz; do
  rm -rf /tmp/ffx /tmp/ff.tar.xz; mkdir -p /tmp/ffx
  if curl -fsSL --retry 3 --retry-all-errors --max-time 240 -o /tmp/ff.tar.xz "$url" \
     && tar -xJf /tmp/ff.tar.xz -C /tmp/ffx; then
    find /tmp/ffx -type f \( -name ffmpeg -o -name ffprobe \) -exec sudo cp {} /usr/local/bin/ \;
    command -v ffmpeg >/dev/null && { ffmpeg -version | head -1; exit 0; }
  fi
  echo "yedek başarısız: $url"
done
echo "::error::ffmpeg kurulamadı"; exit 1

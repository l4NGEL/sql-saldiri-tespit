"""SQL tabanlı ağ saldırısı tespit sistemi (CSE-CIC-IDS2018)."""
import os as _os

# Arrow'un varsayılan (mimalloc) havuzu serbest bırakılan tamponları süreçte tutar; büyük
# akış yüklemelerinde bellek taahhüdü gereksiz şişer. Sistem ayırıcısı belleği hemen iade eder.
_os.environ.setdefault("ARROW_DEFAULT_MEMORY_POOL", "system")

# Прошивки: FPGA і хост

| Файл | Що це |
|---|---|
| `fpga/listener.fs` | бітстрім FPGA для GW2AR-LV18QN88C8/I7 на модулі Sipeed Tang Nano 20K (M1) |
| `fpga/BUILD.txt` | з якого коміту його зібрано, UserCode, частота читання флешу (25 МГц), таймінг збірки |
| `esp32/bootloader.bin`, `esp32/partition-table.bin`, `esp32/listener_fw.bin` | прошивка хоста для ESP32-DevKitC-VIE (M2): завантажувач, таблиця розділів, програма |
| `esp32/BUILD.txt` | з якого коміту її зібрано, її версія (`App version`), ESP-IDF, адреси запису, sha256 кожного файлу |

`tools/make_kit.py --flash` бере сюди лише збірки з закомічених джерел, і тільки якщо в збірці
FPGA запас таймінгу не менше 10 %. `check_all.py` падає, якщо джерела змінилися після цих
збірок.

## Коли заливати

Найкраще до того, як модулі запаяно в плату. Кожен модуль підключається до ноутбука своїм USB,
без плати.

У зібраній платі v2.0 оновлюється лише хост: micro-USB модуля M2 виходить у вікно вхідної кришки.
USB-C модуля FPGA закривають корпуси гнізд RCA (J8, J9), тож бітстрім записати до того, як M1
стане на плату.

## FPGA: Tang Nano 20K

Бітстрім пишеться у SPI-флеш модуля. FPGA читає його звідти щоразу, коли з пробудженням кільця
з'являється 5V_SW, приблизно за 290 мс. Тому запис у флеш переживає вимкнення, а запис у SRAM для
слухача не годиться: він зникає разом із живленням.

### Прошивка відладчика BL616

Міст USB на модулі має власну прошивку. Потрібна версія 2025030317 або новіша: зі старішими
`openFPGALoader` не пише флеш.

- **Як дізнатися версію.**
  - Windows: Диспетчер пристроїв, USB Converter A, Подробиці, «Батьківський»: останні 10 цифр.
  - macOS: `ioreg -p IOUSB -l -w0 | grep -E '"USB Serial Number"|"bcdDevice"'`, останні 10 цифр
    серійного номера.
- **Як оновити.** Програмою BouffaloLabDevCube (Windows і macOS): вибрати чип BL616/618 і вставити
  USB, тримаючи кнопку UPDATE за роз'ємом HDMI. Покроково: wiki.sipeed.com, сторінка
  «update_debugger».

### Windows 10 або 11: Gowin Programmer

1. Gowin Programmer входить у Gowin EDA (Education, з gowinsemi.com) або ставиться окремо з
   пакета Sipeed (dl.sipeed.com, TANG, programmer). Драйвер FTDI ставиться разом із ним.
2. Модуль підключити прямо в порт ПК, без хаба. У Диспетчері пристроїв мають з'явитися
   USB Converter A, USB Converter B і COM-порт.
3. Запустити Programmer:
   - **Cable Setting:** кабель, який він знайшов (USB Debugger A), частота 2.5 МГц або менше,
     Save.
   - **Scan:** у списку вибрати **GW2AR-18C**, бо GW2A-18C і GW2ANR-18C мають той самий ID.
   - Подвійне клацання в колонці Operation, далі:
     - Access Mode: **External Flash Mode**;
     - Operation: **exFlash Erase,Program thru GAO-Bridge**;
     - File: `listener.fs`;
     - External Flash Device: **Generic Flash**;
     - Start Address: **0x000000**.
     Save, потім Program/Configure.
   - Операції з «Verify» Sipeed радить не вибирати: з цим мостом вони бувають дуже повільні або
     обриваються. Перевірка нижче.
4. Те саме з командного рядка, з папки `Programmer\bin`:

   ```bat
   programmer_cli.exe --scan-cables
   programmer_cli.exe --cable-index 4 --frequency 2.5MHz --device GW2AR-18C --run 36 --spiaddr 0x000000 --fsFile C:\шлях\до\kit\2_flash\fpga\listener.fs
   ```

   `--cable-index` береться той, під яким `--scan-cables` показав USB Debugger A.

### macOS (і Apple Silicon): openFPGALoader

1. Встановити Homebrew (brew.sh), далі `brew install openfpgaloader`.
2. Модуль підключити до Mac. На Mac з Apple Silicon на питання про новий аксесуар відповісти
   «Дозволити».
3. Перевірити зв'язок: `openFPGALoader -b tangnano20k --detect`. Має показати idcode 0x0000081b.
4. Записати флеш:

   ```bash
   openFPGALoader -b tangnano20k -f --verify listener.fs
   ```

   Якщо пише «unable to claim usb device», повторити з `sudo`. Драйвер Apple тримає міст, і
   відпустити його може лише root. Вивантажувати драйвер Apple не треба.
5. Висмикнути й вставити USB.

## Хост: ESP32-DevKitC-VIE

Пишеться програмою esptool, однаково з Windows і macOS (і на Apple Silicon).

1. **esptool.** Потрібен Python 3 (`3_laptop/README.md`, «Python»). Далі
   `python -m pip install esptool==5.4.0`. Це та версія, що йде з ESP-IDF 6.1, яким зібрано
   прошивку. На macOS замість `python` писати `python3`.
2. **Порт.** Модуль підключити USB-кабелем (з даними, не лише зарядним).
   - Windows: у Диспетчері пристроїв з'являється COM-порт «Silicon Labs CP210x» або
     «USB-SERIAL CH9102».
   - macOS: `ls /dev/cu.*` показує `/dev/cu.usbserial-…`. Якщо порту немає, треба драйвер моста
     (`3_laptop/README.md`, «Драйвер моста»).
3. **Запис**, з папки `kit/2_flash/esp32` (COM5 замінити на свій порт, на Mac
   `/dev/cu.usbserial-…`):

   ```bash
   python -m esptool --chip esp32 -p COM5 -b 460800 --before default-reset --after hard-reset write-flash --flash-mode dio --flash-size 4MB --flash-freq 40m 0x1000 bootloader.bin 0x8000 partition-table.bin 0x10000 listener_fw.bin
   ```

   Адреси ті самі, що в `BUILD.txt`.
4. **Якщо «Failed to connect».** Тримати кнопку BOOT, коротко натиснути EN, відпустити BOOT і
   повторити.

Налаштування, які хост тримає у флеші (дозвіл підмішування `i`, звук), запис програми не
стирає. На новому модулі підмішування не дозволено.

## Перевірка, що працює саме ця прошивка

- **Хост.** Консоль на 921600 (`3_laptop`: `record`, або будь-який термінал) при старті показує
  `App version:`. Має дорівнювати `version` з `esp32/BUILD.txt`.
- **FPGA через JTAG.** Gowin Programmer, «Read User Code», має показати `usercode` з `fpga/BUILD.txt`.
- **FPGA у платі.** Зі світлом у J1 консоль хоста раз на 10 с показує рядок стану. Числа `packets`
  у ньому ростуть, коли FPGA сконфігурувалася й передає блоки керування хосту.

## Своя збірка

Збирати самому не обов'язково. Хто хоче:
- FPGA: Gowin EDA 1.9.12.03, `python listener_gw/board/build.py` (збирає й перевіряє таймінг);
- хост: ESP-IDF 6.1, `listener_fw/idf.ps1 build`;
- потім закомітити й `python tools/make_kit.py --flash`.

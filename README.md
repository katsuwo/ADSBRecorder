# ADS-B Recorder
Start multiple dump1090s, merge the sockets obtained from them, and record them in sqlite.

Settings are made in the config.yaml file.
Assign unused ports individually for dummyport1 ~ 4 in the config.yaml file.
If you do not set these, dump1090 will not start in --net mode.

dump1090 needs to be pre-installed.

複数のdump1090を起動し、それらから得られるsocketをマージし、sqliteに記録する。
socketはOUTPUTポートへの出力も行う

設定はconfig.yamlファイルにて行う。
config.yamlファイル中のdummyport1~4は未使用ポートを個別にアサインする事。
これらを設定しないとdump1090が--netモードで起動しない。

dump1090は事前にインストールされている必要がある。

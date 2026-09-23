# Сертификаты НУЦ Минцифры

`platform-api2.max.ru` использует TLS-сертификат, выпущенный «Russian Trusted Sub CA»
Минцифры России. Этих корневых сертификатов нет в стандартных наборах (certifi), поэтому
`MAXClient` доверяет системным CA **и** этому файлу.

`russian_trusted_ca.pem` содержит публичные сертификаты:

| Сертификат | SHA-256 | Источник |
|---|---|---|
| Russian Trusted Root CA | `D2:6D:2D:02:31:B7:C3:9F:92:CC:73:85:12:BA:54:10:35:19:E4:40:5D:68:B5:BD:70:3E:97:88:CA:8E:CF:31` | https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt |
| Russian Trusted Sub CA (RSA 2024, до 2029) | — | http://nuc-cdp.digital.gov.ru/cdp/subca_ssl_rsa2024.crt |
| Russian Trusted Sub CA (до 2027) | — | https://gu-st.ru/content/lending/russian_trusted_sub_ca_pem.crt |

Путь к файлу переопределяется переменной `MAX_CA_BUNDLE`.

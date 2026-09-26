import argostranslate.package

print("Обновляю список пакетов...")
argostranslate.package.update_package_index()

packages = argostranslate.package.get_available_packages()

package = next(
    p for p in packages
    if p.from_code == "ru" and p.to_code == "en"
)

print("Скачиваю русский -> английский...")
download_path = package.download()

print("Устанавливаю...")
argostranslate.package.install_from_path(download_path)

print("Готово!")

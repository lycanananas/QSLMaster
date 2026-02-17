pkgname=qslmaster-git
pkgver=1.0.c5a9027.c5a9027.c5a9027
pkgrel=1
pkgdesc="Download QSO data from Wavelog and prepare ADIF output and printable QSL labels"
arch=('any')
url="https://gitlab.com/adrian.grzeca/qslmaster"
license=('GPL3')
depends=('python' 'python-pip')
makedepends=('git')
provides=('qslmaster')
conflicts=('qslmaster')
source=("git+https://gitlab.com/adrian.grzeca/qslmaster.git")
sha256sums=('SKIP')

pkgver() {
  cd "$srcdir/qslmaster"
  base_version=$pkgver
  printf "%s.%s" "$base_version" "$(git rev-parse --short HEAD)"
}

package() {
  cd "$srcdir/qslmaster"
  install -d "$pkgdir/usr/lib/qslmaster"

  pkg_dirs=(
    qslmaster_cli
    qslmaster_gui
    qslmaster_gui/dialogs
    qslmaster_gui/resources
    qslmaster_gui/ui
    qslmaster_gui/utils
    qslmaster_gui/widgets
    qslmaster_gui/workers
  )

  for d in "${pkg_dirs[@]}"; do
    install -d "$pkgdir/usr/lib/qslmaster/$d"
    if compgen -G "$d"/*.py > /dev/null; then
      install -m644 "$d"/*.py "$pkgdir/usr/lib/qslmaster/$d/"
    fi
  done

  if compgen -G qslmaster_gui/resources/*.png > /dev/null; then
    install -m644 qslmaster_gui/resources/*.png "$pkgdir/usr/lib/qslmaster/qslmaster_gui/resources/"
  fi

  python3 -m venv "$pkgdir/usr/lib/qslmaster/venv"
  "$pkgdir/usr/lib/qslmaster/venv/bin/pip" install --no-cache-dir -r "$srcdir/qslmaster/requirements.txt"
  if [[ -f "$srcdir/qslmaster/requirements-gui.txt" ]]; then
    "$pkgdir/usr/lib/qslmaster/venv/bin/pip" install --no-cache-dir -r "$srcdir/qslmaster/requirements-gui.txt"
  fi

  install -Dm644 LICENSE.md "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
  install -Dm644 packaging/qslmaster.desktop "$pkgdir/usr/share/applications/qslmaster.desktop"
  install -Dm644 qslmaster_gui/resources/icon.png "$pkgdir/usr/share/pixmaps/qslmaster.png"
  install -Dm755 packaging/qslmaster "$pkgdir/usr/bin/qslmaster"
  install -Dm755 packaging/qslmaster-cli "$pkgdir/usr/bin/qslmaster-cli"
}

pkgname=qslmaster-git
pkgver=r0.0
pkgrel=1
pkgdesc="Download QSO data from Wavelog and prepare ADIF output and printable QSL labels"
arch=('any')
url="https://gitlab.com/adrian.grzeca/qslmaster"
license=('GPL3')
depends=('python' 'python-requests' 'python-adif-io' 'python-pyhamtools' 'python-reportlab' 'python-pyqt6' 'python-keyring')
makedepends=('git')
provides=('qslmaster')
conflicts=('qslmaster')
source=("git+https://gitlab.com/adrian.grzeca/qslmaster.git")
sha256sums=('SKIP')

pkgver() {
  cd "$srcdir/qslmaster"
  printf "r%s.%s" "$(git rev-list --count HEAD)" "$(git rev-parse --short HEAD)"
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
    install -m644 "$d"/*.py "$pkgdir/usr/lib/qslmaster/$d/"
  done

  install -m644 qslmaster_gui/resources/*.png "$pkgdir/usr/lib/qslmaster/qslmaster_gui/resources/"
  install -Dm644 LICENSE.md "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
  install -Dm644 packaging/qslmaster.desktop "$pkgdir/usr/share/applications/qslmaster.desktop"
  install -Dm644 qslmaster_gui/resources/icon.png "$pkgdir/usr/share/pixmaps/qslmaster.png"
  install -Dm755 packaging/qslmaster "$pkgdir/usr/bin/qslmaster"
  install -Dm755 packaging/qslmaster-cli "$pkgdir/usr/bin/qslmaster-cli"
}

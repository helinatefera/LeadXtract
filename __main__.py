import sys

from loguru import logger as log

from yellowpages import YellowPagesScraperUI

log.remove()


app = YellowPagesScraperUI()
log.add(sys.stdout, level="ERROR", format="\n{message} {file} {line}")

app.mainloop()

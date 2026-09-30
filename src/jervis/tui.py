import curses,time
from .paths import Paths
from .state import State
from .version import __version__
TABS=["DASH","DIALOGUE","PEOPLE","AUDIO","BRAIN","SKILLS","AGENTS","MEMORY","PERMISSIONS","TIMELINE","LOGS","SETTINGS","AUTH"]
def safe(screen,y,x,text,attr=0):
    h,w=screen.getmaxyx()
    if 0<=y<h and 0<=x<w:
        try:screen.addnstr(y,x,text,max(0,w-x-1),attr)
        except curses.error:pass
def run():
    paths=Paths.resolve();paths.ensure();state=State(paths.data/"jervis.sqlite3")
    def app(screen):
        curses.curs_set(0);screen.nodelay(True);tab=0
        while True:
            screen.erase();safe(screen,0,2,"JERVIS CONTROL DECK  v"+__version__,curses.A_BOLD);safe(screen,1,2,"  ".join(("["+name+"]" if i==tab else name) for i,name in enumerate(TABS)))
            safe(screen,3,2,"ACTIVE: "+str(state.get_kv("activity","Idle — waiting for Jervis")));name=TABS[tab]
            if name=="PEOPLE":
                for i,user in enumerate(state.users()[:20]):safe(screen,5+i,2,str(user["name"])+"  role="+str(user["role"])+"  address="+str(user["honorific"] or "not set"))
            elif name=="TIMELINE":
                rows=state._db.execute("SELECT ts,kind,detail FROM events ORDER BY id DESC LIMIT 20").fetchall()
                for i,row in enumerate(rows):safe(screen,5+i,2,time.strftime("%H:%M:%S",time.localtime(row["ts"]))+" "+row["kind"]+": "+row["detail"])
            else:safe(screen,5,2,name+" panel connected to local Jervis state.  arrows navigate · q quit")
            screen.refresh();key=screen.getch()
            if key in (ord("q"),27):break
            if key==curses.KEY_RIGHT:tab=(tab+1)%len(TABS)
            elif key==curses.KEY_LEFT:tab=(tab-1)%len(TABS)
            time.sleep(0.05)
    try:curses.wrapper(app)
    finally:state.close()

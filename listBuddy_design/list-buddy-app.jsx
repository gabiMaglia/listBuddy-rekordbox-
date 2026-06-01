/* List Buddy — interactive prototype (window.ListBuddyApp)
   Variation D · Rack × Dynamic · platform = 'mac' | 'win' */
(function () {
  const { useState, useRef, useEffect } = React;
  const { PL, POOL, ICON, wave } = window.LBDATA;
  const pad2 = n => String(n).padStart(2, '0');
  const PATHS = ['~/Music/USB / Sets', '~/Desktop / Export', '/Volumes/USB-DJ / Crates'];

  const Svg = ({ html, className, style }) =>
    <span className={className} style={style} dangerouslySetInnerHTML={{ __html: html }} />;

  const Meta = ({ p }) => p.bpm == null
    ? <span className="lb-tag">vacía</span>
    : <React.Fragment><span className="lb-tag">{p.genre}</span><span className="lb-tag bpm">{p.bpm} BPM</span></React.Fragment>;

  const Vu = ({ live }) => {
    const h = [10, 16, 22, 26, 19, 12, 24, 17, 9, 14];
    return <div className={'lb-vu' + (live ? ' live' : '')}>
      {h.map((v, i) => <i key={i} style={{ height: v + 'px' }} />)}
    </div>;
  };

  function DonateSheet({ onClose }) {
    return <div className="lb-sheet-wrap" onClick={onClose}>
      <div className="lb-sheet" onClick={e => e.stopPropagation()}>
        <button className="x" onClick={onClose}>✕</button>
        <div className="hd">
          <div className="hicon"><Svg html={ICON.heart} /></div>
          <div><h3>Apoyá List Buddy</h3></div>
        </div>
        <p>List Buddy es gratis. Si te ahorra tiempo armando tus USB y preparando sets, una pequeña ayuda mantiene el proyecto vivo.</p>
        <button className="lb-supbtn"><Svg html={ICON.coffee} />Invitame un café<span className="amt">US$5</span></button>
        <button className="lb-supbtn"><Svg html={ICON.heart} />Donar con PayPal<span className="amt">elegís vos</span></button>
        <button className="lb-supbtn" onClick={onClose}><Svg html={ICON.note} />Seguir gratis</button>
      </div>
    </div>;
  }

  function ListBuddyApp({ platform = 'mac', initialTheme = 'dark' }) {
    const [theme, setTheme] = useState(initialTheme);
    const [pathIx, setPathIx] = useState(0);
    const [order, setOrder] = useState([2, 5, 7]);
    const [phase, setPhase] = useState('idle');     // idle | exporting | done
    const [prog, setProg] = useState(0);
    const [donate, setDonate] = useState(false);
    const timer = useRef(null);
    const path = PATHS[pathIx];

    const can = i => PL[i].n > 0;
    const reset = () => { setPhase('idle'); setProg(0); };
    const toggle = i => {
      if (!can(i) || phase === 'exporting') return;
      reset();
      setOrder(o => o.includes(i) ? o.filter(x => x !== i) : [...o, i]);
    };
    const all = () => { reset(); setOrder(PL.map((_, i) => i).filter(can)); };
    const none = () => { reset(); setOrder([]); };
    const choose = () => { reset(); setPathIx(x => (x + 1) % PATHS.length); };

    const totalFiles = order.reduce((s, i) => s + PL[i].n, 0);
    const selectableCount = PL.filter(p => p.n > 0).length;

    const doExport = () => {
      if (!order.length || phase === 'exporting') return;
      if (phase === 'done') { reset(); return; }
      setPhase('exporting'); setProg(0);
      const t0 = Date.now(), dur = 2200;
      clearInterval(timer.current);
      timer.current = setInterval(() => {
        const p = Math.min(100, ((Date.now() - t0) / dur) * 100);
        setProg(p);
        if (p >= 100) { clearInterval(timer.current); setPhase('done'); }
      }, 40);
    };
    useEffect(() => () => clearInterval(timer.current), []);

    const exporting = phase === 'exporting', done = phase === 'done';

    /* ---- chrome ---- */
    const toggleEl = (
      <div className="lb-toggle" >
        <span className="lb-sun" onClick={() => setTheme('light')}><Svg html={ICON.sun} /></span>
        <span className="lb-moon" onClick={() => setTheme('dark')}><Svg html={ICON.moon} /></span>
      </div>
    );
    const donateBtn = <button className="lb-donate" onClick={() => setDonate(true)}><Svg html={ICON.heart} />Apoyar</button>;

    const titleBar = platform === 'win'
      ? <div className="lb-title win">
          <div className="wtitle"><span className="wicon"><Svg html={ICON.note} /></span>List Buddy</div>
          <div className="wspacer" />
          <div className="wright">{donateBtn}{toggleEl}</div>
          <div className="lb-wctrls">
            <button title="Minimizar"><svg viewBox="0 0 12 12"><line x1="2" y1="6" x2="10" y2="6" stroke="currentColor" strokeWidth="1.3" /></svg></button>
            <button title="Maximizar"><svg viewBox="0 0 12 12"><rect x="2.5" y="2.5" width="7" height="7" fill="none" stroke="currentColor" strokeWidth="1.3" /></svg></button>
            <button className="close" title="Cerrar"><svg viewBox="0 0 12 12"><line x1="2.5" y1="2.5" x2="9.5" y2="9.5" stroke="currentColor" strokeWidth="1.3" /><line x1="9.5" y1="2.5" x2="2.5" y2="9.5" stroke="currentColor" strokeWidth="1.3" /></svg></button>
          </div>
        </div>
      : <div className="lb-title">
          <div className="lb-lights"><i /><i /><i /></div>
          <div className="lb-titletext">List Buddy<span className="lb-ver">1.0</span></div>
          <div className="lb-titleright">{donateBtn}{toggleEl}</div>
        </div>;

    /* ---- output groups ---- */
    const output = order.length === 0
      ? <div className="lb-out-empty">
          <div className="ic"><Svg html={ICON.folderOpen} /></div>
          <div className="t">Sin playlists en cola</div>
          <div className="s">Elegí una o más playlists para ver cómo queda la salida numerada.</div>
        </div>
      : order.map((i, k) => {
          const p = PL[i], tr = (POOL[p.pool] || []).slice(0, 4), more = p.n - tr.length;
          return <div className="lb-grp" key={i}>
            <div className="lb-grp-head">
              <div className="left">
                <span className={'qbadge' + (done ? ' dn' : '')}>{done ? <Svg html={ICON.check} style={{ width: 11, height: 11, display: 'block' }} /> : pad2(k + 1)}</span>
                <span className="fname"><span className="ic"><Svg html={ICON.folder} /></span>{p.name} /</span>
              </div>
              <span className="cnt">{p.n} archivos</span>
            </div>
            <div className="lb-grp-files">
              {tr.map((t, j) => <div className="lb-fileitem" key={j}>
                <span className="idx">{pad2(j + 1)}</span>
                <span className="fn">{pad2(j + 1)} - {t[0]} <span className="ar">— {t[1]}</span><span className="ext">.aiff</span></span>
              </div>)}
            </div>
            {more > 0 && <div className="lb-grp-more">＋ {more} más · numerados 01–{pad2(p.n)}</div>}
          </div>;
        });

    const exportLabel = exporting ? 'Exportando…' : done ? 'Exportar de nuevo' : 'Exportar en orden';

    return <div className={`lb-root lb-${theme} plat-${platform}`} data-variant="4">
      <div className={'lb-win' + (platform === 'win' ? ' win' : '')}>
        {titleBar}
        <div className="lb-body">
          {/* LEFT */}
          <div className="lb-col-l">
            <div className="lb-rackhead">
              <div className="lb-brand">
                <div className="lb-logo"><Svg html={ICON.note} /></div>
                <div><div className="nm">List Buddy</div><div className="sub">Export Engine</div></div>
              </div>
              <Vu live={exporting} />
            </div>

            <div className="lb-dest">
              <div className="lb-eyebrow">Carpeta de destino</div>
              <div className="lb-path clickable" onClick={choose} title="Elegir otra carpeta">
                <span className="lb-folder"><Svg html={ICON.folder} /></span>
                <span className="lb-pathtxt">{path}</span>
              </div>
            </div>

            <div className="lb-sechead">
              <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                <div className="lb-eyebrow">Playlists</div>
                <span className="lb-countpill">{order.length} / {selectableCount}</span>
              </div>
              <div className="lb-actions">
                <button className="lb-btn sm ghost" onClick={all}>Todas</button>
                <button className="lb-btn sm ghost" onClick={none}>Ninguna</button>
              </div>
            </div>

            <div className="lb-cardlist">
              {PL.map((p, i) => {
                const on = order.includes(i), empty = !can(i);
                const ordTxt = on ? pad2(order.indexOf(i) + 1) : pad2(i + 1);
                return <div key={i} className={'lb-card compact' + (on ? ' on' : '') + (empty ? ' empty' : '')} onClick={() => toggle(i)}>
                  <div className="lb-ordernum">{ordTxt}</div>
                  <div className="info"><span className="nm">{p.name}</span><span className="meta"><Meta p={p} /></span></div>
                  <div className="pick">{on && <Svg html={ICON.check} />}</div>
                </div>;
              })}
            </div>

            {(exporting || done) && <div className="lb-prog">
              <div className="lb-proghead">
                <span>{done ? 'Exportación completa' : 'Copiando y numerando…'}</span>
                <b>{Math.round(prog)}%</b>
              </div>
              <div className="lb-meter"><i style={{ '--p': prog + '%' }} /></div>
            </div>}

            <button className="lb-export" onClick={doExport} disabled={!order.length}>
              <span className="num">{pad2(order.length)}</span>{exportLabel}
            </button>
          </div>

          {/* RIGHT */}
          <div className="lb-col-r">
            <div className="lb-sechead" style={{ marginBottom: 10 }}>
              <div className="lb-eyebrow">Salida · vista previa</div>
              <span className="lb-tag bpm">{done ? 'exportado ✓' : order.length ? `${order.length} carpetas · numeración independiente` : 'en espera'}</span>
            </div>
            <div className="lb-output">
              <div className="lb-out-head">
                <div className="lb-out-folder"><span className="ic"><Svg html={ICON.folder} /></span>{path} <span className="lb-mono" style={{ opacity: .7 }}>{totalFiles} archivos</span></div>
              </div>
              <div className="lb-out-list">{output}</div>
            </div>
          </div>
        </div>
        {donate && <DonateSheet onClose={() => setDonate(false)} />}
      </div>
    </div>;
  }

  window.ListBuddyApp = ListBuddyApp;
})();

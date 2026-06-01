/* List Buddy — shared data, icons, helpers (window.LBDATA) */
(function () {
  // track-name pools per vibe (for the numbered-output preview)
  const POOL = {
    techno: [["Don't Go", 'Adam Beyer'], ['Tool of Thought', 'Adam Beyer'], ['Groove', 'Ale Montoya'],
      ['Let Me In', 'Benja Millan'], ['Infinity', 'Bruno (HU)'], ['We Come One', 'CaveX'],
      ['Driving to Nowhere', 'Daniel Sbert'], ['Sonder', 'Dexter White']],
    tech: [['Drift', 'Oscar Mulero'], ['Concrete', 'Rødhåd'], ['Vortex', 'Setaoc Mass'], ['Halo', 'Reeko'],
      ['Static', 'Dax J'], ['Pulse', 'Kobosil']],
    mel: [['Solaris', 'Mind Against'], ['Aurora', 'Tale Of Us'], ['Lykke', 'Kölsch'], ['Distant', 'Massano'],
      ['Horizon', 'Anyma'], ['Echoes', 'Mathame']],
    house: [['Higher', 'Marco Faraone'], ['Sunset', 'Just Emma'], ['Feel It', 'Latmun'], ['Together', 'Rossi.'],
      ['Move', 'Michael Bibi'], ['Lately', 'PAWSA']],
    minimal: [['Resonate', 'Cera Alba'], ['Patterns', 'Archie Hamilton'], ['Hold', 'Enzo Siragusa'],
      ['Loop', 'Rich NxT'], ['Drama', 'Seb Zito'], ['Subtle', 'Rossko']],
    disco: [['Boogie', 'Folamour'], ['Groovin', 'Mr Scruff'], ['Nightfall', 'Crackazat'], ['Shine', 'Pete Herbert'],
      ['Velvet', 'Demuir'], ['Glow', 'Jad & The'], ],
  };

  const PL = [
    { name: 'MinimalDeepWarm', n: 132, genre: 'Minimal',  bpm: 124, pool: 'minimal' },
    { name: 'housepost',       n: 19,  genre: 'House',    bpm: 122, pool: 'house' },
    { name: 'techDeFondo',     n: 27,  genre: 'Techno',   bpm: 130, pool: 'tech' },
    { name: 'tech1',           n: 41,  genre: 'Techno',   bpm: 132, pool: 'techno' },
    { name: 'techhouse2',      n: 14,  genre: 'TecHouse', bpm: 126, pool: 'house' },
    { name: 'marerook',        n: 80,  genre: 'Melodic',  bpm: 120, pool: 'mel' },
    { name: '45set',           n: 17,  genre: 'Disco',    bpm: 118, pool: 'disco' },
    { name: 'm1',              n: 160, genre: 'Techno',   bpm: 134, pool: 'techno' },
    { name: 'CUE Analysis',    n: 0,   genre: '—',        bpm: null, pool: null },
  ];

  const ICON = {
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>',
    folder:'<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
    sun:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19"/></svg>',
    moon:  '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>',
    note:  '<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M9 18V6l10-2v12"/><circle cx="6.5" cy="18" r="2.6"/><circle cx="16.5" cy="16" r="2.6"/></svg>',
    heart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20.5S3.5 15 3.5 8.8A4.3 4.3 0 0 1 12 7a4.3 4.3 0 0 1 8.5 1.8C20.5 15 12 20.5 12 20.5z"/></svg>',
    coffee:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h13v5a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4z"/><path d="M17 9h2.5a2.5 2.5 0 0 1 0 5H17"/><path d="M6 2v2M10 2v2M14 2v2"/></svg>',
    folderOpen:'<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2H3z"/><path d="M3 9l1.6 8a2 2 0 0 0 2 1.6h11a2 2 0 0 0 2-1.6L21 9"/></svg>',
  };

  // pseudo-random vertical-bar waveform (decorative)
  function wave(w, h, n, seed) {
    let s = seed || 7, bars = '', bw = w / n;
    for (let i = 0; i < n; i++) {
      s = (s * 9301 + 49297) % 233280;
      const r = s / 233280;
      const env = Math.sin((i / n) * Math.PI);
      const bh = Math.max(2, (0.18 + r * 0.82) * h * (0.4 + env * 0.6));
      bars += `<rect x="${(i * bw).toFixed(1)}" y="${((h - bh) / 2).toFixed(1)}" width="${(bw * 0.46).toFixed(1)}" height="${bh.toFixed(1)}" rx="1"/>`;
    }
    return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${bars}</svg>`;
  }

  window.LBDATA = { PL, POOL, ICON, wave };
})();

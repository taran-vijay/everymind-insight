/* Checkbox-only data options. Source files and selections stay in memory only. */
(() => {
  'use strict';
  const byId = id => document.getElementById(id);
  const blank = () => ({schema_version:'1.0.0',exclusions:[],numeric_rules:[],rule_logic:'any',categorical_exclusions:{county:[],role:[],language:[],training_month:[]},speed_seconds:30,long_seconds:7200});
  const filterOptions = [
    {id:'speeders',label:'Finished in under 30 seconds'},
    {id:'long_duration',label:'Took longer than 2 hours'},
    {id:'large_drops',label:'A drop of four points from before to after'},
    {id:'invalid_training_date',label:'Missing or invalid training date'},
  ];
  let spec = blank(), metadata = null, backend = false, rowMode = false, canApply = false;
  let pendingFile = null, aggregate = null, previewSerial = 0, timer = 0, busy = false, opening = false, sourceChosen = false;
  const copy = value => JSON.parse(JSON.stringify(value));
  const dialog = byId('data-options');
  const el = (tag, text = '', className = '') => {
    const n = document.createElement(tag); n.textContent = text; n.className = className; return n;
  };
  const count = n => n == null ? 'Withheld' : Number(n).toLocaleString();
  function updateOpenButton() {
    const selected = rowMode && spec.exclusions.length > 0;
    byId('open-full-report').textContent = selected ? 'Open filtered report' : rowMode || !aggregate ? 'Open full report' : 'Open report unchanged';
    byId('open-full-report').disabled = busy || opening || !!pendingFile || (rowMode ? selected && !canApply : !aggregate);
  }
  function setBusy(value) {
    busy = value;
    byId('close-data-options').disabled = value;
    for (const id of ['report-picker','source-sheet']) byId(id).disabled = value;
    byId('start-report').disabled = value || !pendingFile;
    byId('options-controls').disabled = value || !rowMode;
    dialog.setAttribute('aria-busy',String(value));
    updateOpenButton();
  }
  async function request(path, body) {
    const response = await fetch(`./api/${path}`, {method:'POST',headers:{'Content-Type':'application/json','X-Input-Hash':metadata?.input_hash || ''},body:JSON.stringify(body)});
    if (!response.ok) {
      let message = 'The request could not be completed. Your current report is unchanged.';
      try { const data = await response.json(); message = Array.isArray(data.detail) ? data.detail.map(v=>v.msg).join(' ') : data.detail || message; } catch {}
      throw new Error(message);
    }
    return response.json();
  }
  function renderOptions() {
    const blocked = busy || opening || !!pendingFile;
    byId('options-controls').disabled = blocked || !rowMode;
    byId('options-controls').hidden = !rowMode || !!pendingFile;
    byId('options-impact').hidden = !rowMode || !!pendingFile;
    byId('start-report').disabled = busy || opening || !pendingFile;
    for(const id of ['report-picker','source-sheet'])byId(id).disabled = busy || opening;
    byId('options-source-note').textContent = pendingFile
      ? 'Use the selected file to review its data options.' : rowMode
      ? `${count(metadata.total)} responses. Check any responses to leave out.`
      : aggregate ? 'Data options are unavailable for an aggregate JSON report because it has no row-level source. You can open it unchanged, or choose an XLSX/CSV using the local survey server.'
      : 'Choose a survey export or aggregate report to continue.';
    const options = byId('exclusion-options'); options.replaceChildren();
    for (const option of rowMode ? filterOptions : []) {
      const row = el('div','','exclusion-row');
      const label = el('label','','option-check'); const input = el('input'); input.type='checkbox'; input.checked=spec.exclusions.includes(option.id); input.dataset.option=option.id;
      label.append(input,document.createTextNode(option.label));
      if(option.id==='speeders') {
        const duration=metadata.fields?.find(field=>field.id==='duration_seconds');
        label.title='Completion time minus Start time, in seconds.' + (duration?.min != null ? ` Shortest completion in this file: ${duration.min.toLocaleString()} seconds.` : '');
      }
      const total = el('span','Checking…','option-count'); total.dataset.optionCount=option.id;
      input.addEventListener('change',()=>{ spec.exclusions = input.checked ? [...spec.exclusions,option.id] : spec.exclusions.filter(id=>id!==option.id); queuePreview(); });
      row.append(label,total);
      options.append(row);
    }
    updateOpenButton();
  }
  function queuePreview() {
    clearTimeout(timer); const serial=++previewSerial;
    byId('options-error').textContent='';
    canApply=false;updateOpenButton();
    if(!rowMode || pendingFile || opening)return;
    byId('impact-counts').textContent='Checking the selected options…';
    byId('impact-help').textContent='';
    for(const node of dialog.querySelectorAll('[data-option-count]'))node.textContent='Checking…';
    timer=setTimeout(()=>refreshPreview(serial),200);
  }
  async function refreshPreview(serial) {
    try {
      const result=await request('preview',spec);
      if(serial!==previewSerial || !dialog.open || pendingFile || opening)return;
      byId('impact-counts').textContent=`Included: ${count(result.kept)}. Removed: ${result.removed_label}. Full source: ${count(result.total)}.`;
      byId('impact-help').textContent=result.message;
      for(const node of dialog.querySelectorAll('[data-option-count]'))node.textContent=count(result.option_counts[node.dataset.optionCount]);
      canApply=result.can_apply;updateOpenButton();
    } catch(error) {
      if(serial!==previewSerial)return;
      byId('options-error').textContent=error.message;canApply=false;updateOpenButton();
    }
  }
  function openOptions() {
    if(busy || opening)return;
    renderOptions();byId('options-error').textContent='';
    byId('report-start').open = !!pendingFile || (!rowMode && !aggregate);
    dialog.showModal();
    byId(pendingFile ? 'start-report' : rowMode || aggregate ? 'open-full-report' : 'report-picker').focus();
    queuePreview();
  }
  async function loadSource() {
    if(busy || opening || !pendingFile)return;
    opening=true;
    clearTimeout(timer);++previewSerial;renderOptions();byId('close-data-options').disabled=true;
    byId('source-error').textContent='';
    try {
      await window.everymindBackendReady;
      if(pendingFile) {
        if(pendingFile.name.toLowerCase().endsWith('.json')) {
          aggregate=ReportData.validate(JSON.parse(await pendingFile.text()));rowMode=false;spec=blank();
          byId('source-selection').textContent='Aggregate report ready. Open it unchanged, or choose a survey to enable data options.';
        } else {
          if(!backend)throw new Error('To analyze XLSX or CSV files, start the local survey server. Aggregate JSON reports can be opened directly.');
          if(pendingFile.size>50*1024*1024)throw new Error('Choose a survey smaller than 50 MB.');
          byId('source-selection').textContent='Reading your survey locally…';
          const query=new URLSearchParams({filename:pendingFile.name});const sheet=byId('source-sheet').value.trim();if(sheet)query.set('sheet',sheet);
          const response=await fetch(`./api/source?${query}`,{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:pendingFile});
          const data=await response.json();if(!response.ok)throw new Error(data.detail || 'The survey could not be read.');
          metadata=data;rowMode=true;aggregate=null;spec=blank();
          byId('source-selection').textContent=`Survey ready: ${count(metadata.total)} responses. Data stays on this computer.`;
        }
        sourceChosen=true;pendingFile=null;byId('report-picker').value='';
      }
      byId('options-error').textContent='';
    } catch(error) {byId('source-error').textContent=error.message;}
    finally {
      opening=false;renderOptions();byId('close-data-options').disabled=false;
      if(!pendingFile){byId('open-full-report').focus();queuePreview();}
    }
  }
  async function openReport() {
    if(busy || opening || pendingFile || (!rowMode && !aggregate) || (rowMode && spec.exclusions.length && !canApply))return;
    setBusy(true);clearTimeout(timer);++previewSerial;byId('options-error').textContent='';
    const chosen=copy(spec);
    try {
      const next=rowMode?await request('report',chosen):aggregate;
      if(!next)throw new Error('Choose a survey or aggregate report first.');
      const ok=await window.EveryMindReport.load(async()=>next,{rowSource:rowMode});
      if(!ok)throw new Error('The returned report could not be opened. Your previous report is unchanged.');
      spec=copy(chosen);dialog.close();
      document.querySelector('nav a[data-view="overview"]').click();
    }catch(error){byId('options-error').textContent=error.message;}
    finally{setBusy(false);if(dialog.open)queuePreview();}
  }
  document.addEventListener('click',event=>{
    if(event.target.closest('#open-report-options')){event.preventDefault();openOptions();}
    if(event.target.closest('#start-report')){event.preventDefault();loadSource();}
  });
  document.addEventListener('change',event=>{
    if(event.target.id!=='report-picker')return;
    pendingFile=event.target.files[0] || null;
    if(pendingFile)byId('source-selection').textContent=`Selected: ${pendingFile.name}. Choose Use this file to continue.`;
    clearTimeout(timer);++previewSerial;renderOptions();queuePreview();
  });
  byId('close-data-options').addEventListener('click',()=>{if(!busy && !opening){clearTimeout(timer);++previewSerial;dialog.close();}});
  dialog.addEventListener('cancel',event=>{if(busy || opening)event.preventDefault();else{clearTimeout(timer);++previewSerial;}});
  byId('open-full-report').addEventListener('click',openReport);
  window.EveryMindDataOptions={reportOpened(report,sourceAvailable){sourceChosen=true;aggregate=report;rowMode=sourceAvailable && !!metadata?.available;if(!rowMode){spec=blank();byId('source-selection').textContent='Aggregate report opened. Choose an XLSX or CSV survey to enable data options.';}}};
  window.everymindBackendReady.then(data=>{
    backend=!!data;
    if(sourceChosen)return;
    metadata=data?.available?data:null;rowMode=!!metadata;
    if(metadata)byId('source-selection').textContent=`Survey ready: ${count(metadata.total)} responses. Choose another file only to change the source.`;
    if(!rowMode && !aggregate)aggregate=window.EveryMindReport.current();
    if(dialog.open){renderOptions();queuePreview();}
  });
})();

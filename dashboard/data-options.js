/* Data-options UI. Source files, specifications and undo stay in memory only. */
(() => {
  'use strict';
  const byId = id => document.getElementById(id);
  const blank = () => ({schema_version:'1.0.0',exclusions:[],numeric_rules:[],rule_logic:'any',categorical_exclusions:{county:[],role:[],language:[],training_month:[]},speed_seconds:30,long_seconds:7200});
  let spec = blank(), applied = blank(), undo = [], metadata = null, backend = false, rowMode = false;
  let pendingFile = null, aggregate = null, previewSerial = 0, timer = 0, busy = false, opening = false;
  const copy = value => JSON.parse(JSON.stringify(value));
  const dialog = byId('data-options');
  const el = (tag, text = '', className = '') => {
    const n = document.createElement(tag); n.textContent = text; n.className = className; return n;
  };
  const count = n => n == null ? 'Withheld' : Number(n).toLocaleString();
  function remember() { undo.push(copy(spec)); if (undo.length > 30) undo.shift(); byId('undo-data-options').disabled = !undo.length; }
  function changed() { byId('apply-data-options').disabled = true; queuePreview(); }
  function setBusy(value) {
    busy = value;
    for (const id of ['open-full-report','apply-data-options','reset-data-options','undo-data-options','close-data-options']) byId(id).disabled = value;
    byId('options-controls').disabled = value || !rowMode;
    dialog.setAttribute('aria-busy',String(value));
  }
  async function request(path, body, blob = false) {
    const response = await fetch(`./api/${path}`, {method:'POST',headers:{'Content-Type':'application/json','X-Input-Hash':metadata?.input_hash || ''},body:JSON.stringify(body)});
    if (!response.ok) {
      let message = 'The request could not be completed. Your current report is unchanged.';
      try { const data = await response.json(); message = Array.isArray(data.detail) ? data.detail.map(v=>v.msg).join(' ') : data.detail || message; } catch {}
      throw new Error(message);
    }
    return blob ? response.blob() : response.json();
  }
  function makeSelect(options, value, label) {
    const select = el('select'); select.setAttribute('aria-label',label);
    for (const [id,text] of options) { const option = el('option',text); option.value=id; select.append(option); }
    select.value=value; return select;
  }
  function renderOptions() {
    byId('options-controls').disabled = !rowMode;
    byId('apply-data-options').hidden = !rowMode;
    byId('options-impact').hidden = !rowMode;
    byId('open-full-report').textContent = rowMode ? 'Open full report (nothing removed)' : 'Open report unchanged';
    byId('options-source-note').textContent = rowMode
      ? `${count(metadata.total)} responses with usable IDs. Nothing is removed unless you choose an option.`
      : 'Data options are unavailable for an aggregate JSON report because it has no row-level source. You can open it unchanged, or choose an XLSX/CSV using the local survey server.';
    const options = byId('exclusion-options'); options.replaceChildren();
    for (const option of rowMode ? metadata.options : []) {
      const row = el('div','','exclusion-row');
      const label = el('label','','option-check'); const input = el('input'); input.type='checkbox'; input.checked=spec.exclusions.includes(option.id); input.dataset.option=option.id;
      label.append(input,document.createTextNode(option.label));
      const total = el('span','Checking…','option-count'); total.dataset.optionCount=option.id;
      input.addEventListener('change',()=>{ remember(); spec.exclusions = input.checked ? [...spec.exclusions,option.id] : spec.exclusions.filter(id=>id!==option.id); changed(); });
      row.append(label,total);
      if (option.id==='speeders' || option.id==='long_duration') {
        const field = option.id==='speeders' ? 'speed_seconds' : 'long_seconds';
        const thresholdLabel = el('label',option.id==='speeders' ? 'Under (seconds)' : 'Longer than (seconds)','threshold-label');
        const threshold = el('input'); threshold.type='number'; threshold.min='0.01'; threshold.max=field==='speed_seconds' ? '604800' : '31536000'; threshold.step='any'; threshold.value=spec[field];
        threshold.addEventListener('input',()=>{ remember(); spec[field]=threshold.valueAsNumber; changed(); }); thresholdLabel.append(threshold); row.append(thresholdLabel);
      }
      options.append(row);
    }
    byId('rule-logic').value = spec.rule_logic;
    renderRules(); renderCategories();
    byId('undo-data-options').disabled = !undo.length;
    for (const button of dialog.querySelectorAll('[data-export]')) button.disabled = !rowMode;
  }
  function renderRules(focusLabel = null) {
    const list = byId('numeric-rules'); list.replaceChildren();
    spec.numeric_rules.forEach((rule,index)=>{
      const row = el('div','','numeric-rule');
      const field = makeSelect((metadata?.fields || []).map(f=>[f.id,f.label]),rule.field,`Field for rule ${index+1}`);
      const operator = makeSelect([['below','is below'],['above','is above'],['between','is between (inclusive)'],['outside','is outside'],['equals','equals'],['missing','is missing']],rule.operator,`Operator for rule ${index+1}`);
      const heading = el('p',`Remove responses where`); row.append(heading,field,operator);
      const entry = metadata?.fields.find(f=>f.id===rule.field);
      const values = rule.values ?? (rule.value == null ? [] : [rule.value]);
      const required = rule.operator==='missing' ? 0 : ['between','outside'].includes(rule.operator) ? 2 : 1;
      for (let i=0;i<required;i++) {
        const input=el('input'); input.type=entry?.type==='date' ? 'date' : 'number'; input.step='any'; input.value=values[i] ?? '';
        input.setAttribute('aria-label',`${i===0?'Value or lower bound':'Upper bound'} for rule ${index+1}`);
        input.addEventListener('input',()=>{
          remember(); const next=[...values]; next[i]=entry?.type==='date' ? input.value : input.valueAsNumber;
          if (required===1) {rule.value=next[0];delete rule.values;} else {rule.values=next;delete rule.value;}
          // Update the captured values so editing both bounds keeps the first edit.
          values[i]=next[i]; changed();
        }); row.append(input);
      }
      field.addEventListener('change',()=>{ remember(); rule.field=field.value; delete rule.value;delete rule.values; renderRules(field.getAttribute('aria-label'));changed(); });
      operator.addEventListener('change',()=>{ remember(); rule.operator=operator.value;delete rule.value;delete rule.values;renderRules(operator.getAttribute('aria-label'));changed(); });
      const remove=el('button',`Remove rule ${index+1}`,'button'); remove.type='button'; remove.addEventListener('click',()=>{remember();spec.numeric_rules.splice(index,1);renderRules();changed();}); row.append(remove);
      if (entry) {
        const region=el('div','','field-histogram');
        const table=el('table'); const caption=el('caption',`${entry.label}: coarse histogram. Small bins are merged.`);table.append(caption);
        const body=el('tbody'); const maximum=Math.max(1,...entry.histogram.map(b=>b.count));
        for (const bin of entry.histogram) {
          const tr=el('tr'); const label=el('th',`${typeof bin.lower==='number'?Number(bin.lower.toFixed(1)):bin.lower} – ${typeof bin.upper==='number'?Number(bin.upper.toFixed(1)):bin.upper}`);label.scope='row';
          const graphic=el('td'); const bar=el('span','','histogram-bar');bar.style.width=`${100*bin.count/maximum}%`;bar.setAttribute('aria-hidden','true');graphic.append(bar);
          tr.append(label,graphic,el('td',count(bin.count)));body.append(tr);
        }
        table.append(body);region.append(table); if(!entry.histogram.length)region.append(el('p','The histogram is withheld to protect small groups.'));row.append(region);
      }
      list.append(row);
    });
    if(focusLabel) [...list.querySelectorAll('select')].find(n=>n.getAttribute('aria-label')===focusLabel)?.focus();
  }
  function renderCategories() {
    const groups=byId('category-options');groups.replaceChildren();
    for (const [field,values] of Object.entries(rowMode ? metadata.categories : {})) {
      const fieldset=el('fieldset');fieldset.append(el('legend',{county:'Training-affiliated county',role:'Role',language:'Language',training_month:'Training month'}[field]));
      if (!values.length) fieldset.append(el('p','No categories can be shown safely.'));
      for (const value of values) {
        const label=el('label','','option-check');const input=el('input');input.type='checkbox';input.checked=spec.categorical_exclusions[field].includes(value.id);
        input.addEventListener('change',()=>{remember();const selected=spec.categorical_exclusions[field];spec.categorical_exclusions[field]=input.checked?[...selected,value.id]:selected.filter(v=>v!==value.id);changed();});
        label.append(input,document.createTextNode(`${value.id} (${count(value.count)})`));fieldset.append(label);
      } groups.append(fieldset);
    }
  }
  function queuePreview() {
    clearTimeout(timer); const serial=++previewSerial;
    byId('options-error').textContent='';
    byId('apply-data-options').disabled=true;
    for(const button of dialog.querySelectorAll('[data-export]'))button.disabled=true;
    if(!rowMode)return;
    byId('impact-counts').textContent='Checking the selected options…';
    byId('headline-preview').replaceChildren();byId('impact-help').textContent='';
    for(const node of dialog.querySelectorAll('[data-option-count]'))node.textContent='Checking…';
    timer=setTimeout(()=>refreshPreview(serial),200);
  }
  async function refreshPreview(serial) {
    try {
      const result=await request('preview',spec);
      if(serial!==previewSerial || !dialog.open)return;
      byId('impact-counts').textContent=`Included: ${count(result.kept)}. Removed: ${result.removed_label}. Full source: ${count(result.total)}.`;
      byId('impact-help').textContent=result.message;
      for(const node of dialog.querySelectorAll('[data-option-count]'))node.textContent=count(result.option_counts[node.dataset.optionCount]);
      byId('apply-data-options').disabled=!result.can_apply || busy;
      for(const button of dialog.querySelectorAll('[data-export]'))button.disabled=!result.can_apply || busy;
      const target=byId('headline-preview');target.replaceChildren();
      const labels={identify_crises:'Identify challenges and crises',describe_988:'Describe 988',know_when_to_use_988:'Know when to use 988'};
      for(const entry of result.headlines)target.append(el('p',`${labels[entry.skill]} — ${entry.measure==='agree_after'?'current':'recalled-before'} agreement: ${count(entry.before)} of ${count(entry.base_before)} → ${count(entry.after)} of ${count(entry.base_after)}.`));
    } catch(error) {
      if(serial!==previewSerial)return;
      byId('options-error').textContent=error.message;byId('apply-data-options').disabled=true;
      for(const button of dialog.querySelectorAll('[data-export]'))button.disabled=true;
    }
  }
  async function openOptions() {
    if(busy || opening)return;
    opening=true;
    for(const id of ['open-report-options','start-report','report-picker','source-sheet'])byId(id).disabled=true;
    byId('source-error').textContent='';
    try {
      if(pendingFile) {
        if(pendingFile.name.toLowerCase().endsWith('.json')) {
          aggregate=ReportData.validate(JSON.parse(await pendingFile.text()));rowMode=false;spec=blank();undo=[];
        } else {
          if(!backend)throw new Error('To analyze XLSX or CSV files, start the local survey server. Aggregate JSON reports can be opened directly.');
          if(pendingFile.size>50*1024*1024)throw new Error('Choose a survey smaller than 50 MB.');
          byId('source-selection').textContent='Reading your survey locally…';
          const query=new URLSearchParams({filename:pendingFile.name});const sheet=byId('source-sheet').value.trim();if(sheet)query.set('sheet',sheet);
          const response=await fetch(`./api/source?${query}`,{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:pendingFile});
          const data=await response.json();if(!response.ok)throw new Error(data.detail || 'The survey could not be read.');
          metadata=data;rowMode=true;aggregate=null;spec=blank();applied=blank();undo=[];
          byId('source-selection').textContent=`Survey ready: ${count(metadata.total)} responses. Data stays on this computer.`;
        }
        pendingFile=null;byId('report-picker').value='';
      }
      if(!rowMode && !aggregate) {
        byId('report-start').scrollIntoView({block:'center'});byId('report-picker').focus();
        if(!metadata?.available)throw new Error('Choose a survey export or aggregate JSON report first.');
      }
      renderOptions();byId('options-error').textContent='';dialog.showModal();byId('open-full-report').focus();queuePreview();
    } catch(error) {byId('source-error').textContent=error.message;}
    finally {opening=false;for(const id of ['open-report-options','start-report','report-picker','source-sheet'])byId(id).disabled=false;}
  }
  async function openReport(full) {
    if(busy)return;
    setBusy(true);clearTimeout(timer);++previewSerial;byId('options-error').textContent='';
    const chosen=full?blank():copy(spec);
    try {
      const next=rowMode?await request('report',chosen):aggregate;
      if(!next)throw new Error('Choose a survey or aggregate report first.');
      const ok=await window.EveryMindReport.load(async()=>next,{rowSource:rowMode});
      if(!ok)throw new Error('The returned report could not be opened. Your previous report is unchanged.');
      applied=copy(chosen);spec=copy(chosen);undo=[];dialog.close();
      document.querySelector('nav a[data-view="overview"]').click();
    }catch(error){byId('options-error').textContent=error.message;}
    finally{setBusy(false);byId('undo-data-options').disabled=!undo.length;if(dialog.open)queuePreview();}
  }
  document.addEventListener('click',event=>{
    const trigger=event.target.closest('#open-report-options, #start-report');
    if(trigger){event.preventDefault();openOptions();}
  });
  document.addEventListener('change',event=>{
    if(event.target.id!=='report-picker')return;
    pendingFile=event.target.files[0] || null;
    if(pendingFile)byId('source-selection').textContent=`Selected: ${pendingFile.name}. Choose Open report to review your options.`;
  });
  byId('close-data-options').addEventListener('click',()=>{if(!busy){clearTimeout(timer);++previewSerial;dialog.close();}});
  dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault();else{clearTimeout(timer);++previewSerial;}});
  byId('open-full-report').addEventListener('click',()=>openReport(true));
  byId('apply-data-options').addEventListener('click',()=>openReport(false));
  byId('reset-data-options').addEventListener('click',()=>{remember();spec=blank();renderOptions();changed();});
  byId('undo-data-options').addEventListener('click',()=>{if(!undo.length)return;spec=undo.pop();renderOptions();changed();});
  byId('rule-logic').addEventListener('change',event=>{remember();spec.rule_logic=event.target.value;changed();});
  byId('add-numeric-rule').addEventListener('click',()=>{if(spec.numeric_rules.length>=30)return;remember();spec.numeric_rules.push({field:'duration_seconds',operator:'below',value:30});renderRules();changed();});
  for(const button of dialog.querySelectorAll('[data-export]'))button.addEventListener('click',async()=>{
    button.disabled=true;byId('options-error').textContent='';
    try {
      const blob=await request(`export/${button.dataset.export}`,spec,true);const url=URL.createObjectURL(blob);const anchor=el('a');anchor.href=url;anchor.download=`everymind-report.${button.dataset.export}`;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    } catch(error){byId('options-error').textContent=error.message;}finally{queuePreview();}
  });
  window.EveryMindDataOptions={reportOpened(report,sourceAvailable){aggregate=report;rowMode=sourceAvailable && !!metadata?.available;if(!rowMode){spec=blank();applied=blank();undo=[];byId('source-selection').textContent='Aggregate report opened. Choose an XLSX or CSV survey to enable data options.';}}};
  window.everymindBackendReady.then(data=>{
    backend=!!data;metadata=data?.available?data:null;rowMode=!!metadata;
    if(metadata)byId('source-selection').textContent=`Survey ready: ${count(metadata.total)} responses. Choose Open report to review your options.`;
    if(!rowMode && !aggregate)aggregate=window.EveryMindReport.current();
  });
})();

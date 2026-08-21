fetch('reports/opportunities.csv')
.then(r=>r.text())
.then(t=>{
 const rows=t.split('\n').slice(1);
 const table=document.getElementById('table');
 rows.filter(x=>x.trim()).forEach(r=>{
   let c=r.split(',');
   table.innerHTML += `<tr><td>${c[0]||''}</td><td>${c[1]||''}</td><td>${c[2]||''}</td></tr>`;
 });
})
.catch(e=>console.log(e));

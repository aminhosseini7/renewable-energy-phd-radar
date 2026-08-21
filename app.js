let data=[];
fetch('reports/opportunities.json')
.then(r=>r.json())
.then(x=>{data=x;show(x);});

function show(arr){
let t=document.getElementById('rows');
t.innerHTML='';
arr.forEach(o=>{
t.innerHTML+=`<tr><td>${o.title}</td><td>${o.university}</td><td>${o.country}</td><td>${o.score}</td></tr>`;
});
}
document.getElementById('search').onkeyup=e=>{
let q=e.target.value.toLowerCase();
show(data.filter(x=>JSON.stringify(x).toLowerCase().includes(q)));
}
let data=[];

async function load(){

try{

let response=await fetch("../reports/opportunities.csv");
let text=await response.text();

let lines=text.trim().split("\n");
let headers=lines[0].split(",");

data=lines.slice(1).map(line=>{

let values=line.split(",");

let obj={};

headers.forEach((h,i)=>{
obj[h]=values[i] || "";
});

return obj;

});

render();

}catch(e){

document.getElementById("results").innerHTML=
"<tr><td colspan='7'>No report generated yet. Run Daily PhD Radar workflow.</td></tr>";

}

}


function render(){

let search=document.getElementById("search").value.toLowerCase();
let country=document.getElementById("country").value;
let funding=document.getElementById("funding").value;


let filtered=data.filter(x=>{

let text=JSON.stringify(x).toLowerCase();

return (
(!search || text.includes(search)) &&
(!country || x.country===country) &&
(!funding || x.funding===funding)
);

});


let html="";

filtered
.sort((a,b)=>(Number(b.score)||0)-(Number(a.score)||0))
.forEach(x=>{

html+=`

<tr>

<td>${x.title || x.source}</td>

<td>${x.country}</td>

<td class="score">${x.score}%</td>

<td>${x.funding}</td>

<td>${x.deadline}</td>

<td>${x.matches}</td>

<td>
<a href="${x.url}" target="_blank">
Open
</a>
</td>

</tr>

`;

});


document.getElementById("results").innerHTML=html;

}


document.getElementById("search").oninput=render;
document.getElementById("country").onchange=render;
document.getElementById("funding").onchange=render;

load();

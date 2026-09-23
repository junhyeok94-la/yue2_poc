const test=require('node:test');
const assert=require('node:assert/strict');
const {moveSection,removeSection}=require('../ui/song-editor.js');
test('move preserves IDs, content and original array',()=>{
 const a=[{id:'a',lyrics:['한글']},{id:'b',lyrics:['후렴']}];
 const b=moveSection(a,'a',1);
 assert.deepEqual(b.map(s=>s.id),['b','a']);
 assert.deepEqual(a.map(s=>s.id),['a','b']);
 assert.equal(b[1].lyrics[0],'한글');
 assert.deepEqual(moveSection(a,'a',-1),a);
});
test('delete targets identity, preserves other contents',()=>{
 const a=[{id:'a',lyrics:['one']},{id:'b',lyrics:['two']}];
 assert.deepEqual(removeSection(a,'a'),[{id:'b',lyrics:['two']}]);
 assert.equal(a.length,2);
});

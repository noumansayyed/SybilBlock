const {expect}=require("chai");const {ethers}=require("hardhat");
describe("SybilTrustRegistry",function(){
 async function setup(){const [owner,other]=await ethers.getSigners();const F=await ethers.getContractFactory("SybilTrustRegistry");const c=await F.deploy();return{c,owner,other};}
 it("stores a score",async function(){const{c}=await setup();const id=ethers.keccak256(ethers.toUtf8Bytes("demo"));await c.updateTrustScore(id,76,"rf-v1");const r=await c.getAccountRecord(id);expect(r[0]).to.equal(76);expect(r[2]).to.equal("rf-v1");expect(r[3]).to.equal(true);});
 it("restricts updates to owner",async function(){const{c,other}=await setup();const id=ethers.keccak256(ethers.toUtf8Bytes("demo"));await expect(c.connect(other).updateTrustScore(id,50,"rf-v1")).to.be.revertedWith("Not authorized");});
 it("rejects scores above 100",async function(){const{c}=await setup();const id=ethers.keccak256(ethers.toUtf8Bytes("demo"));await expect(c.updateTrustScore(id,101,"rf-v1")).to.be.revertedWith("Invalid score");});
});

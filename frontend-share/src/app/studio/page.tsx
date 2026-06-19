"use client";
import dynamic from 'next/dynamic';


const Page = dynamic(()=>import('./studio-app'),{ssr:false,});

export default Page;
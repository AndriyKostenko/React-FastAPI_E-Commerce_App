const FormWrap = ({children}: {children: React.ReactNode}) => {
    return ( 
        <div className="min-h-fit
                        h-full
                        flex
                        items-center
                        justify-center
                        pb-12
                        pt-16
                        ">
            <div className="liquid-glass
                            max-w-[520px]
                            w-full
                            flex
                            flex-col
                            gap-6
                            items-center
                            p-8
                            md:p-10">
                {children}
            </div>
        </div>
     );
}
 
export default FormWrap;
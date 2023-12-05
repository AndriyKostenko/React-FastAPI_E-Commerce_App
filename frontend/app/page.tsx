import  Container  from "./components/Container";
import HomeBanner from "./components/banner/HomeBanner";


export default function Home() {
	return (
		<div className="p-8">
			<Container>
				<div>
					<HomeBanner/>
				</div>
			</Container>
		</div>
	)
};

#pragma once
class ini_parser
{
public:
	ini_parser();
	~ini_parser();
	void			init(std::string path);

	int				get_int(std::string sec, std::string key);
	void			set_int(std::string sec, std::string key, int val);

	double			get_double(std::string sec, std::string key);
	void			set_double(std::string sec, std::string key, double val);

	std::string		get_string(std::string sec, std::string key);
	void			set_string(std::string sec, std::string key, std::string val);

private:
	std::string _ini_path;
};


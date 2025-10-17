using LLVMSharp.Interop;
using ParserModule.Nodes;

namespace CodeGenModule;

public sealed class ExternFunctionGenerator
{
    private readonly LLVMModuleRef _module;
    private readonly Dictionary<string, FunctionSymbol> _functions;
    private readonly TypeVisitor _typeVisitor = new();

    public ExternFunctionGenerator(LLVMModuleRef module, Dictionary<string, FunctionSymbol> functions)
    {
        _module = module;
        _functions = functions;
    }

    public void Generate(ExternFunctionDeclarationNode node)
    {
        var signature = node.Signature;
        var name = signature.Name;
        var returnType = signature.ReturnType;
        var returnTypeRef = LLVMTypeRef.Void;
        if (returnType != null)
        {
            returnType.Accept(_typeVisitor);
            returnTypeRef = _typeVisitor.Type;
        }
        
        var parameters = signature.Parameters;
        Span<LLVMTypeRef> paramTypeRefs = stackalloc LLVMTypeRef[parameters.Count];
        for (var i = 0; i < parameters.Count; i++)
        {
            parameters[i].Type.Accept(_typeVisitor);
            paramTypeRefs[i] = _typeVisitor.Type;
        }
        
        var funcTypeRef = LLVMTypeRef.CreateFunction(returnTypeRef, paramTypeRefs, false);
        var funcValueRef = _module.AddFunction(name, funcTypeRef);
        _functions.Add(name, new FunctionSymbol(funcTypeRef, funcValueRef));
    }
}